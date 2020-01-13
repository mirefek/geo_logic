import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
import cairo
import numpy as np
from geo_object import *
from parse import Parser, type_to_c
from tools import ToolError, ToolErrorException, MovableTool
import primitive_pred
from logic_model import LogicModel
from collections import defaultdict
from tool_step import ToolStep, ToolStepEnv, proof_checker

def corners_to_rectangle(corners):
    size = corners[1] - corners[0]
    return list(corners[0])+list(size)

class Drawing(Gtk.Window):

    def make_toolbox(self, max_height = 45):
        self.tool_buttons = dict()
        self.parser = Parser()
        self.parser.parse_file("tools.gl")
        self.tool_dict = self.parser.tool_dict
        self.tool_dict['line', (Point, Point)].add_symmetry((1,0))
        self.tool_dict['midpoint', (Point, Point)].add_symmetry((1,0))
        self.tool_dict['dist', (Point, Point)].add_symmetry((1,0))
        self.tool_dict['intersection', (Line, Line)].add_symmetry((1,0))
        self.tool_dict['intersection0', (Circle, Circle)].add_symmetry((1,0))
        self.tool_dict['intersection_remoter', (Circle, Circle, Point)].add_symmetry((1,0,2))

        tool_names = set()
        self.name_to_itypes = defaultdict(list)
        for key, tool in self.tool_dict.items():
            if not isinstance(key, tuple): continue
            name, itype = key
            tool_names.add(name)
            if isinstance(tool, MovableTool): itype = itype[2:]
            self.name_to_itypes[name].append(itype)
        tool_names = sorted(tool_names)

        def change_tool(button, name):
            if button.get_active() and True:
                self.tool = self.scripted_tool
                self.tool_data = []
                self.tool_name = name
                self.tool_itypes = self.name_to_itypes[name]

                # printing type
                ttypes = []
                for itype in self.tool_itypes:
                    args = ' '.join(type_to_c[t] for t in itype)
                    if (name,itype) not in self.tool_dict:
                        itype = (float, float)+itype
                        movable_mark = '<M> '
                    else: movable_mark = ''
                    otype = self.tool_dict[name,itype].out_types
                    output = ' '.join(type_to_c[t] for t in otype)
                    ttypes.append("{}{} -> {}".format(movable_mark, args, output))
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
            self.tool_buttons[name] = button
            vbox.add(button)
        return hbox

    def __init__(self):
        super(Drawing, self).__init__()
        proof_checker.paralelize()
        self.shift = np.array([0,0])
        self.scale = 1
        self.mb_grasp = None
        self.steps = []
        self.obj_to_step = []
        self.steps_refresh()
        self.key_to_tool = {
            'p': "perp_bisector",
            '2': "midpoint",
            'f': "free_point",
            'l': "line",
            'c': "circle",
            'x': "intersection0",
            '9': "circle9",
            'i': "incircle",
            'e': "excircle",
            't': "double_dir_test",
            'o': "circumcenter",
        }

        hbox = Gtk.HPaned()
        hbox.add(self.make_toolbox())
        self.parser.parse_file("construction.gl")
        loaded_tool = self.tool_dict['_', ()]
        self.steps = loaded_tool.assumptions
        for i,step in enumerate(self.steps):
            self.obj_to_step += [i]*len(step.tool.out_types)
        self.steps_refresh()

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

        self.tool = None
        self.tool_data = []
        self.tool = self.scripted_tool
        self.tool_name = "free_point"
        self.tool_itypes = self.name_to_itypes[self.tool_name]

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
                step.meta_args = tuple(self.get_coor(e))
                self.steps_refresh()
                self.darea.queue_draw()
        if e.state & Gdk.ModifierType.BUTTON2_MASK:
            if self.mb_grasp is None: return
            self.shift = np.array([e.x, e.y])/self.scale - self.mb_grasp
            self.darea.queue_draw()

    def steps_refresh(self):
        proof_checker.reset()
        self.model = LogicModel()
        self.step_env = ToolStepEnv(self.model)
        self.step_env.run_steps(self.steps, 1, catch_errors = True)

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

        for ti,li,obj in self.point_sets():
            obj.draw(cr, corners, self.scale)
        for ti,li,obj in self.points():
            obj.draw(cr, corners, self.scale)

    def on_key_press(self,w,e):

        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        #print(keyval_name)
        if keyval_name == 'm':
            self.tool = self.move_tool
            print("Move tool")
            self.tool_data = None
        elif keyval_name == 'h':
            self.tool = self.hide_tool
            print("Hide tool")
            self.tool_data = None
        elif keyval_name == 'BackSpace':
            print("BACK")
            if not self.steps:
                print("No more steps to undo")
                return
            step = self.steps.pop()
            if len(step.tool.out_types) > 0:
                del self.obj_to_step[-len(step.tool.out_types):]
            self.steps_refresh()
            self.darea.queue_draw()
        elif keyval_name == 'F2':
            i = 0
            for step in self.steps:
                i2 = i+len(step.tool.out_types)
                tokens = ['x{}'.format(x) for x in range(i,i2)]
                tokens.append('<-')
                tokens.append(step.tool.name)
                tokens.extend(map(str, step.meta_args))
                tokens.extend('x{}'.format(x) for x in step.local_args)
                print('  '+' '.join(tokens))
                i = i2
        elif keyval_name == "Escape":
            #proof_checker.stop()
            Gtk.main_quit()
        elif keyval_name in self.key_to_tool:
            tool_name = self.key_to_tool[keyval_name]
            print(tool_name)
            self.tool_buttons[tool_name].set_active(True)
        else:
            #print(keyval_name)
            return False

    def on_button_press(self, w, e):

        coor = self.get_coor(e)
        if e.button == 1 and self.tool is not None:
            if e.type != Gdk.EventType.BUTTON_PRESS: return
            self.tool(coor)
            self.darea.queue_draw()
        if e.button == 2:
            self.mb_grasp = coor

    def scripted_tool(self, coor):
        obj = self.select_obj(coor)
        if obj is None: self.tool_data = []
        else: self.tool_data.append(obj)

        type_list = tuple(
            self.model.obj_types[self.step_env.local_to_global[x]]
            for x in self.tool_data
        )
        tool = self.tool_dict.get((self.tool_name, type_list), None)
        if tool is None: tool = self.tool_dict.get((self.tool_name, (float, float)+type_list), None)
        if tool is None and len(self.tool_data) == 1:
            tool = self.tool_dict.get((self.tool_name, (float, float)), None)
            if tool is not None:
                self.tool_data = []
                type_list = []
        if tool is not None:
            print("tool_data: {}".format(' '.join(type_to_c[x] for x in type_list)))
            print("APPLY")
            if isinstance(tool, MovableTool):
                meta_args = tuple(coor)
            else: meta_args = ()
            step = ToolStep(tool, meta_args, self.tool_data)

            try:
                self.step_env.run_steps((step,), 1)
                self.obj_to_step += [len(self.steps)]*len(step.tool.out_types)
                self.steps.append(step)
            except ToolError as e:
                if isinstance(e, ToolErrorException): raise e.e
                print("Construction failed: {}".format(e))
                self.steps_refresh()

            self.tool_data = []
            type_list = []
        else:
            n = len(type_list)
            if all(itype[:n] != type_list
                   for itype in self.tool_itypes):
                self.tool_data = []
                type_list = []

        print("tool_data: {}".format(' '.join(type_to_c[x] for x in type_list)))

    def move_tool(self, coor):
        _,p = self.closest_point(coor)
        if p is None:
            tool_data = None
            print("No point under cursor")
            return
        step_i = self.obj_to_step[p]
        step = self.steps[step_i]
        if isinstance(step.tool, MovableTool): self.tool_data = step
        else:
            self.tool_data = None
            print("Point is not movable")

    def hide_tool(self, coor):
        TODO_later
        obj = self.select_obj(coor)
        if obj is None: return
        self.constr.hide(obj)
        self.darea.queue_draw()

    def objs_of_type(self, obj_type):
        used = set()
        for top_level_i, logic_i in enumerate(self.step_env.local_to_global):
            if logic_i is None: continue
            if not issubclass(self.model.obj_types[logic_i], obj_type): continue
            logic_i = self.model.ufd.obj_to_root(logic_i)
            if logic_i in used: continue
            used.add(logic_i)
            yield top_level_i, logic_i, self.model.num_model[logic_i]

    def points(self):
        return self.objs_of_type(Point)
    def point_sets(self):
        return self.objs_of_type(PointSet)

    def closest_obj_of_type(self, coor, obj_type):

        obj_dist = [
            (obj.dist_from(coor), ti)
            for (ti,li,obj) in self.objs_of_type(obj_type)
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
