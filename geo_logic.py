import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
import cairo
import numpy as np
from geo_object import *
from parse_tools import ToolBox, type_to_c
from tool_base import ToolError, PrimitivePred
import primitive_pred
from logic_model import LogicModel
from collections import defaultdict
from construction import *

def corners_to_rectangle(corners):
    size = corners[1] - corners[0]
    return list(corners[0])+list(size)

class Drawing(Gtk.Window):

    def make_toolbox(self, max_height = 45):
        self.toolbox = ToolBox()
        self.toolbox.load_file("tools2.txt", False)

        tool_names = set()
        name_to_itypes = defaultdict(list)
        for name, itype in self.toolbox.tool_dict.keys():
            tool_names.add(name)
            name_to_itypes[name].append(itype)
        tool_names = sorted(tool_names)

        def change_tool(button, name):
            if button.get_active() and True:
                self.tool = self.scripted_tool
                self.tool_data = []
                self.tool_name = name
                self.tool_itypes = name_to_itypes[name]

                # printing type
                ttypes = []
                for itype in self.tool_itypes:
                    args = ' '.join(type_to_c[t] for t in itype)
                    _, otype = self.toolbox.tool_dict[name,itype]
                    output = ' '.join(type_to_c[t] for t in otype)
                    ttypes.append("{} -> {}".format(args, output))
                print("Tool '{} : {}'".format(name, ', or '.join(ttypes)))

        num_names = len(tool_names)
        num_columns = (num_names-1) // max_height + 1
        max_height = (num_names-1) // num_columns + 1

        hbox = Gtk.HBox()
        counter = max_height
        button1 = None
        vbox = None
        for name in tool_names:
            if counter == max_height:
                vbox = Gtk.VBox()
                hbox.add(vbox)
                counter = 0
            counter += 1
            if button1 is None:
                button1 = Gtk.RadioButton.new_with_label_from_widget(button1, name)
                button = button1
            else:
                button = Gtk.RadioButton.new_from_widget(button1)
                button.set_label(name)
            button.connect("toggled", change_tool, name)
            vbox.add(button)
        return hbox

    def __init__(self):
        super(Drawing, self).__init__()
        self.shift = np.array([0,0])
        self.scale = 1
        self.mb_grasp = None
        self.constr = Construction()

        hbox = Gtk.HPaned()
        hbox.add(self.make_toolbox())

        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                              Gdk.EventMask.KEY_PRESS_MASK |
                              Gdk.EventMask.SCROLL_MASK |
                              Gdk.EventMask.BUTTON1_MOTION_MASK |
                              Gdk.EventMask.BUTTON2_MOTION_MASK )
        hbox.add(self.darea)
        self.add(hbox)

        self.darea.connect("button-press-event", self.on_button_press)
        self.darea.connect("scroll-event", self.on_scroll)
        self.darea.connect("motion-notify-event", self.on_motion)
        self.connect("key-press-event", self.on_key_press)

        self.set_title("Drawing")
        self.resize(1200, 400)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", Gtk.main_quit)
        self.show_all()

        self.tool = self.point_tool
        self.tool_data = []

    def get_coor(self, e):
        return np.array([e.x, e.y])/self.scale - self.shift
        
    def on_scroll(self,w,e):
        coor = self.get_coor(e)
        if e.direction == Gdk.ScrollDirection.DOWN: self.scale *= 0.9
        elif e.direction == Gdk.ScrollDirection.UP: self.scale /= 0.9
        print("zoom {}".format(self.scale))
        self.shift = np.array([e.x, e.y])/self.scale - coor
        self.darea.queue_draw()

    def on_motion(self,w,e):
        if e.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.tool == self.move_tool and self.tool_data is not None:
                step = self.tool_data
                assert(isinstance(step, ConstrMovable))
                step.coor = self.get_coor(e)
                self.constr.refresh()
                self.darea.queue_draw()
        if e.state & Gdk.ModifierType.BUTTON2_MASK:
            if self.mb_grasp is None: return
            self.shift = np.array([e.x, e.y])/self.scale - self.mb_grasp
            self.darea.queue_draw()

    def on_draw(self, wid, cr):

        corners = np.array([
            [0, 0],
            [self.darea.get_allocated_width(), self.darea.get_allocated_height()],
        ])/self.scale - self.shift
        cr.scale(self.scale, self.scale)
        cr.translate(*self.shift)
        cr.rectangle(*corners_to_rectangle(corners))
        cr.set_source_rgb(1, 1, 1)
        cr.fill()

        for obj in self.point_sets():
            obj.draw(cr, corners, self.scale)
        for obj in self.points():
            obj.draw(cr, corners, self.scale)

    def on_key_press(self,w,e):

        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        #print(keyval_name)
        if keyval_name == 'p':
            self.tool = self.point_tool
            print("Point tool")
            self.tool_data = []
        elif keyval_name == 'd':
            self.tool = self.dep_point_tool
            print("Dependent point tool")
            self.tool_data = []
        elif keyval_name == 'm':
            self.tool = self.move_tool
            print("Move tool")
            self.tool_data = None
        elif keyval_name == 'h':
            self.tool = self.hide_tool
            print("Hide tool")
            self.tool_data = None
        elif keyval_name == 'BackSpace':
            print("BACK")
            self.constr.pop()
            self.darea.queue_draw()
        elif keyval_name == "Escape":
            Gtk.main_quit()
        else:
            return False

    def on_button_press(self, w, e):

        coor = self.get_coor(e)
        if e.button == 1:
            if e.type != Gdk.EventType.BUTTON_PRESS: return
            self.tool(coor)
            self.darea.queue_draw()
        if e.button == 2:
            self.mb_grasp = coor

    def point_tool(self, coor):
        ConstrFreePoint(self.constr, coor)

    def dep_point_tool(self, coor):
        _,ps_num = self.closest_set(coor)
        if ps_num is None: return

        ConstrDepPoint(self.constr, coor, ps_num)

    def scripted_tool(self, coor):
        obj = self.select_obj(coor)
        if obj is None: self.tool_data = []
        else:
            self.tool_data.append(obj)
            type_list = tuple(type(x) for x in self.tool_data)
            tool, _ = self.toolbox.tool_dict.get((self.tool_name, type_list), (None,None))
            if tool is not None:
                print("APPLY")
                print("tool_data: {}".format(' '.join(type_to_c[type(x)] for x in self.tool_data)))
                ConstrTool(self.constr, tool, self.tool_data)

                self.tool_data = []
            else:
                n = len(type_list)
                if all(itype[:n] != type_list
                       for itype in self.tool_itypes):
                    self.tool_data = []

        print("tool_data: {}".format(' '.join(type_to_c[type(x)] for x in self.tool_data)))

    def move_tool(self, coor):
        _,p = self.closest_point(coor)
        if p is None:
            tool_data = None
            print("No point under cursor")
        step_i,_ = self.constr.to_constr_index(p)
        step = self.constr.steps[step_i]
        if isinstance(step, ConstrMovable): self.tool_data = step
        else:
            self.tool_data = None
            print("Point is not movable")

    def hide_tool(self, coor):
        obj = self.select_obj(coor)
        if obj is None: return
        self.constr.hide(obj)
        self.darea.queue_draw()

    def objs_of_type(self, obj_type):
        objs = (self.constr.num_model[n] for n in self.constr.visible_li)
        objs = filter(lambda obj: obj is not None and isinstance(obj, obj_type), objs)
        return objs

    def points(self):
        return self.objs_of_type(Point)
    def point_sets(self):
        return self.objs_of_type(PointSet)

    def closest_obj_of_type(self, coor, obj_type):

        obj_dist = [
            (obj.dist_from(coor), obj)
            for obj in self.objs_of_type(obj_type)
        ]
        if len(obj_dist) == 0: return 0, None
        return min(obj_dist, key = lambda x: x[0])

    def closest_point(self, coor):
        return self.closest_obj_of_type(coor, Point)

    def closest_set(self, coor):
        return self.closest_obj_of_type(coor, PointSet)

    def select_obj(self, coor, point_radius = 20, ps_radius = 20):
        d,p = self.closest_point(coor)
        if d*self.scale < point_radius: return p
        d,ps = self.closest_set(coor)
        if d*self.scale < ps_radius: return ps
        return None

if __name__ == "__main__":
    win = Drawing()
    Gtk.main()
