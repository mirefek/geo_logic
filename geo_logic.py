import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import cairo
import numpy as np
from geo_object import *
from parse import Parser, type_to_c
from tools import ToolError, ToolErrorException, MovableTool
import primitive_pred
from logic_model import LogicModel
from collections import defaultdict
from tool_step import ToolStep, ToolStepEnv, proof_checker
from file_chooser import select_file_open, select_file_save
from relstr import TriggerEnv, RelStr
from stop_watch import print_times

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
        self.shift = np.array([0,0])
        self.scale = 1
        self.mb_grasp = None
        self.steps = []
        self.obj_to_step = []
        self.key_to_tool = {
            'p': "perp_bisector",
            '2': "midpoint",
            'f': "free_point",
            'l': "line",
            'c': "circle",
            'C': "compass",
            'x': "intersection0",
            '9': "circle9",
            'i': "incircle",
            'e': "excircle",
            'o': "circumcenter",
            'X': "intersection_remoter",
            'd': "point_on",
            'question': "lies_on",
            'exclam': "line_uq",
            '1': "radius_dist",
            '2': "on_circle_by_dist",
            '3': "cong_sss",
            '4': "collinear_by_angle",
            't': "circumcircle_uq",
        }
        self.default_fname = None

        hbox = Gtk.HPaned()
        hbox.add(self.make_toolbox())

        self.triggers = self.make_triggers()
        self.steps_refresh()

        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                              Gdk.EventMask.KEY_PRESS_MASK |
                              Gdk.EventMask.SCROLL_MASK |
                              Gdk.EventMask.BUTTON1_MOTION_MASK |
                              Gdk.EventMask.BUTTON2_MOTION_MASK )
        self.darea_vbox = Gtk.VBox()
        self.darea_vbox.add(self.darea)
        self.progress_bar = Gtk.ProgressBar(show_text=False)
        self.darea_vbox.pack_end(self.progress_bar, False, False, 0)
        hbox.add(self.darea_vbox)
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

        def update_progress_bar(done, size):
            if size == 0: self.progress_bar.set_fraction(0)
            else: self.progress_bar.set_fraction(done / size)
            return False
        def update_progress_bar_idle(done, size):
            GLib.idle_add(update_progress_bar, done, size)
        proof_checker.paralelize(progress_hook = update_progress_bar_idle)

    def load_file(self, fname):
        if fname is None: return
        self.default_fname = fname
        self.parser.parse_file(fname)
        loaded_tool = self.tool_dict['_', ()]
        del self.tool_dict['_', ()]
        self.steps = loaded_tool.assumptions
        self.obj_to_step = []
        for i,step in enumerate(self.steps):
            self.obj_to_step += [i]*len(step.tool.out_types)
        self.steps_refresh()

    def save_file(self, fname):
        if fname is None: return
        self.default_fname = fname
        with open(fname, 'w') as f:
            f.write('_ ->\n')
            i = 0
            for step in self.steps:
                i2 = i+len(step.tool.out_types)
                tokens = ['x{}'.format(x) for x in range(i,i2)]
                tokens.append('<-')
                tokens.append(step.tool.name)
                tokens.extend(map(str, step.meta_args))
                tokens.extend('x{}'.format(x) for x in step.local_args)
                f.write('  '+' '.join(tokens)+'\n')
                i = i2

    def make_triggers(self):
        triggers = TriggerEnv()
        lies_on_l = self.tool_dict['lies_on', (Point, Line)]
        lies_on_c = self.tool_dict['lies_on', (Point, Circle)]
        radius_of = self.tool_dict['radius_of', (Circle,)]
        direction_of = self.tool_dict['direction_of', (Line,)]
        center_of = self.tool_dict['center_of', (Circle,)]
        dist_pp = self.tool_dict['dist', (Point, Point)]
        radius_dist = self.tool_dict['radius_dist', (Point, Circle)]

        p2l2 = RelStr()
        p2l2.add_rel(lies_on_l, ('A','l'))
        p2l2.add_rel(lies_on_l, ('A','m'))
        p2l2.add_rel(lies_on_l, ('B','l'))
        p2l2.add_rel(lies_on_l, ('B','m'))
        def p2l2_trig(d):
            A, B, l, m = d['A'], d['B'], d['l'], d['m']
            if A == B or l == m: return
            #print("p2l2_trig", A, B, l, m)
            if not self.model.num_model[A].identical_to(self.model.num_model[B]):
                #print("glue lines")
                self.model.glue(l, m)
            elif not self.model.num_model[l].identical_to(self.model.num_model[m]):
                #print("glue points")
                self.model.glue(A, B)
        triggers.add(p2l2, p2l2_trig)

        p3c2 = RelStr()
        p3c2.add_rel(lies_on_c, ('A','b'))
        p3c2.add_rel(lies_on_c, ('A','c'))
        p3c2.add_rel(lies_on_c, ('B','b'))
        p3c2.add_rel(lies_on_c, ('B','c'))
        p3c2.add_rel(lies_on_c, ('C','b'))
        p3c2.add_rel(lies_on_c, ('C','c'))
        def p3c2_trig(d):
            A, B, C, b, c = d['A'], d['B'], d['l'], d['m']
            if A == B or B == C or C == A or l == m: return
            #print("p2l2_trig", A, B, l, m)
            nA, nB, nC = (self.model.num_model[x] for x in (A, B, C))
            if not (A.identical_to(B) or A.identical_to(C) or B.identical_to(C)):
                self.model.glue(b, c)
        triggers.add(p3c2, p3c2_trig)

        pal2 = RelStr()
        pal2.add_rel(lies_on_l, ('A','l'))
        pal2.add_rel(lies_on_l, ('A','m'))
        pal2.add_rel(direction_of, ('l','d'))
        pal2.add_rel(direction_of, ('m','d'))
        def pal2_trig(d):
            l, m = d['l'], d['m']
            if l != m: self.model.glue(l, m)
        triggers.add(pal2, pal2_trig)

        on_circ = RelStr()
        on_circ.add_rel(lies_on_c, ('A','c'))
        on_circ.add_rel(radius_of, ('c','r'))
        on_circ.add_rel(center_of, ('c','C'))
        def on_circ_trig(d):
            A, c = d['A'], d['c']
            #print("on_circ_trig", A, c)
            radius_dist.run((), (A, c), self.model, 1)
        triggers.add(on_circ, on_circ_trig)

        rad_dist = RelStr()
        rad_dist.add_rel(radius_of, ('c','r'))
        rad_dist.add_rel(center_of, ('c','C'))
        rad_dist.add_rel(dist_pp, ('C','A','r'))
        def rad_dist_trig(d):
            c, r, C, A = d['c'], d['r'], d['C'], d['A']
            #print("rad_dist_trig", c, r, C, A)
            lies_on_c.run((), (A, c), self.model, 0)
        triggers.add(rad_dist, rad_dist_trig)

        return triggers

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
        self.model = LogicModel(self.triggers)
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
        ctrl = (e.state & Gdk.ModifierType.CONTROL_MASK)
        if keyval_name == 'm':
            self.tool = self.move_tool
            print("Move tool")
            self.tool_data = None
        elif keyval_name == 'h':
            TODO
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
        elif keyval_name == "Escape":
            print_times()
            Gtk.main_quit()
        elif ctrl and keyval_name == 'o':
            fname = select_file_open(self)
            self.load_file(fname)
            self.darea.queue_draw()
        elif ctrl and keyval_name == 'S':
            fname = select_file_save(self)
            self.open_file(fname)
        elif ctrl and keyval_name == 's':
            fname = self.default_fname
            if fname is None: fname = select_file_save(self)
            self.save_file(fname)
        elif not ctrl and keyval_name in self.key_to_tool:
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
                print("correct")
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
