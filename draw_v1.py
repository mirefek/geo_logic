import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
import cairo
import numpy as np
from geo_object import *
from construction_v1 import *
import constr_tools as tls

def corners_to_rectangle(corners):
    size = corners[1] - corners[0]
    return list(corners[0])+list(size)

class Drawing(Gtk.Window):

    def make_toolbox(self):
        tls.parse_tools('tools.txt')
        tool_names = sorted(tls.tool_dict.keys())
        button1 = None
        def change_tool(button, name):
            if button.get_active():
                self.tool = self.scripted_tool
                self.tool_data = []
                self.scr_tool = tls.tool_dict[name]

                # printing type
                ttypes = []
                for tool in tls.tool_dict[name]:
                    args = ' '.join(map(tls.t_to_s, tool.itypes))
                    output = ' '.join(map(tls.t_to_s, tool.otypes))
                    ttypes.append("{} -> {}".format(args, output))
                print("Tool '{} : {}'".format(name, ', or '.join(ttypes)))

        vbox = Gtk.VBox()
        for name in tool_names:
            if button1 is None:
                button1 = Gtk.RadioButton.new_with_label_from_widget(button1, name)
                button = button1
            else:
                button = Gtk.RadioButton.new_from_widget(button1)
                button.set_label(name)
            button.connect("toggled", change_tool, name)
            vbox.add(button)
        return vbox

    def __init__(self):
        super(Drawing, self).__init__()
        self.shift = np.array([0,0])
        self.scale = 1
        self.visible = set()
        self.mb_grasp = None

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
        self.resize(600, 400)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", Gtk.main_quit)
        self.show_all()

        self.constr = Construction()
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
        elif keyval_name == 'l':
            self.tool = self.line_tool
            print("Line tool")
            self.tool_data = []
        elif keyval_name == 'c':
            self.tool = self.circle_tool
            print("Circle tool")
            self.tool_data = []
        elif keyval_name == 'd':
            self.tool = self.dep_point_tool
            print("Dependent point tool")
            self.tool_data = []
        elif keyval_name == 'i':
            self.tool = self.intersection_tool
            print("Intersection tool")
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
            if len(self.visible) > 0:
                self.visible.discard(max(self.visible))
            if len(self.visible) > 0: i = max(self.visible)+1
            else: i = 0
            self.constr.truncate(i)
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
        new_obj = self.constr.add(ConstrPoint, coor)
        if new_obj is not None: self.visible.add(new_obj.index)

    def scripted_tool(self, coor):
        obj = self.select_obj(coor)
        if obj is None: self.tool_data = []
        else:
            self.tool_data.append(obj)
            tool = None
            type_list = [type(x) for x in self.tool_data]
            for t in reversed(self.scr_tool):
                if t.can_apply(type_list):
                    tool = t
                    break
            if tool is not None:
                print("tool_data: {}".format(' '.join(map(tls.o_to_ts, self.tool_data))))
                ori_len = len(self.constr)
                output = tool.apply(self.constr, self.tool_data)
                if None in output:
                    print("construction failed")
                    self.constr.truncate(ori_len)
                else:
                    for obj in output: self.visible.add(obj.index)
                self.tool_data = []
            else:
                if all(not t.can_apply(type_list, partial = True)
                       for t in self.scr_tool):
                    self.tool_data = []

        print("tool_data: {}".format(' '.join(map(tls.o_to_ts, self.tool_data))))

    def line_tool(self, coor):
        dist, p = self.closest_point(coor)
        if p is None: return
        if len(self.tool_data) == 0: self.tool_data.append(p)
        else:
            p0 = self.tool_data[0]
            new_obj = self.constr.add(ConstrLine, p0, p)
            if new_obj is not None: self.visible.add(new_obj.index)
            self.tool_data = []

    def circle_tool(self, coor):
        dist, p = self.closest_point(coor)
        if p is None: return
        if len(self.tool_data) == 1 and p == self.tool_data[0]: return

        self.tool_data.append(p)
        print("  {} points".format(len(self.tool_data)))
        if len(self.tool_data) == 3:
            new_obj = self.constr.add(ConstrCirc, *self.tool_data)
            if new_obj is not None: self.visible.add(new_obj.index)
            self.tool_data = []
            #print("circle made")

    def intersection_tool(self, coor):
        point_sets = [(ps.dist_from(coor), ps)
                      for ps in self.point_sets()]
        if len(point_sets) < 2: return
        ps1 = min(point_sets, key = lambda x: x[0])
        point_sets.remove(ps1)
        ps2 = min(point_sets, key = lambda x: x[0])
        ps1 = ps1[1]
        ps2 = ps2[1]
        if isinstance(ps1, Line) and isinstance(ps2, Line):
            new_obj = self.constr.add(ConstrIntersectionUniq, ps1, ps2)
        else:
            new_obj = self.constr.add(ConstrIntersectionFlex, coor, ps1, ps2)
        if new_obj is not None: self.visible.add(new_obj.index)

    def dep_point_tool(self, coor):
        _,ps = self.closest_set(coor)
        if ps is None: return
        new_obj = self.constr.add(ConstrDepPoint, coor, ps)
        if new_obj is not None: self.visible.add(new_obj.index)

    def move_tool(self, coor):
        _,p = self.closest_point(coor)
        obj = self.constr.steps[p.index]
        if isinstance(obj, ConstrMovable): self.tool_data = obj
        else:
            print("not possible to move", p, self.tool_data)
            self.tool_data = None

    def hide_tool(self, coor):
        obj = self.select_obj(coor)
        if obj is None: return
        self.visible.discard(obj.index)
        self.darea.queue_draw()

    def objs_of_type(self, obj_type, visible_only = True):
        if visible_only: objs = (self.constr.obj_list[n] for n in self.visible)
        else: objs = self.constr.obj_list
        objs = filter(lambda obj: obj is not None and isinstance(obj, obj_type), objs)
        return objs

    def points(self, visible_only = True):
        return self.objs_of_type(Point, visible_only)
    def point_sets(self, visible_only = True):
        return self.objs_of_type(PointSet, visible_only)

    def closest_obj_of_type(self, coor, obj_type, visible_only = True):

        obj_dist = [
            (obj.dist_from(coor), obj)
            for obj in self.objs_of_type(obj_type, visible_only)
        ]
        if len(obj_dist) == 0: return 0, None
        return min(obj_dist, key = lambda x: x[0])

    def closest_point(self, coor, visible_only = True):
        return self.closest_obj_of_type(coor, Point, visible_only)

    def closest_set(self, coor, visible_only = True):
        return self.closest_obj_of_type(coor, PointSet, visible_only)

    def select_obj(self, coor, visible_only = True, point_radius = 20, ps_radius = 20):
        d,p = self.closest_point(coor)
        if d*self.scale < point_radius: return p
        d,ps = self.closest_set(coor)
        if d*self.scale < ps_radius: return ps
        return None

if __name__ == "__main__":
    win = Drawing()
    Gtk.main()
