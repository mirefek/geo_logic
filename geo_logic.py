import gi as gtk_import
gtk_import.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import cairo
import numpy as np
from geo_object import *
from parse import Parser, type_to_c
import primitive_pred
from collections import defaultdict
from tool_step import ToolStep, proof_checker
from file_chooser import select_file_open, select_file_save
from stop_watch import print_times, StopWatch
from triggers import ImportedTools
from itertools import islice
from view_port_ori import ViewPort
from graphical_env import GraphicalEnv
from tools import MovableTool

class Drawing(Gtk.Window):

    def make_toolbox(self, max_height = 45):
        self.tool_buttons = dict()
        self.parser = Parser()
        self.parser.parse_file("basic.gl")
        basic_tools = ImportedTools(self.parser.tool_dict)
        self.parser.parse_file("macros.gl", axioms = False, basic_tools = basic_tools)
        self.imported_tools = ImportedTools(self.parser.tool_dict)
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
        self.view_port = ViewPort()
        self.mb_grasp = None
        self.key_to_tool = {
            'p': "perp_bisector",
            'f': "free_point",
            #'l': "p_line",
            'l': "line",
            #'c': "p_circum",
            'c': "circle",
            'C': "compass",
            '9': "circle9",
            'i': "incircle",
            'e': "excircle",
            'o': "circumcircle",
            #'x': "p_intersect",
            #'X': "p_intersect_rem",
            'x': "intersection",
            'X': "intersection_remoter",
            'd': "point_on",
            'question': "lies_on",
            'slash': "midpoint",
            #'exclam': "fake_lies_on",
            '1': "point_on_circle",
            '2': "point_to_circle",
            '3': "cong_sss",
            't': "test",
        }
        self.default_fname = None

        hbox = Gtk.HPaned()
        hbox.add(self.make_toolbox())

        self.env = GraphicalEnv(self.imported_tools)

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
        self.env.set_steps(loaded_tool.assumptions)

    def save_file(self, fname):
        if fname is None: return
        print("saving to '{}'".format(fname))
        self.default_fname = fname
        with open(fname, 'w') as f:
            f.write('_ ->\n')
            i = 0
            for step in self.env.steps:
                i2 = i+len(step.tool.out_types)
                tokens = ['x{}'.format(x) for x in range(i,i2)]
                tokens.append('<-')
                tokens.append(step.tool.name)
                tokens.extend(map(str, step.meta_args))
                tokens.extend('x{}'.format(x) for x in step.local_args)
                f.write('  '+' '.join(tokens)+'\n')
                i = i2

    def get_coor(self, e):
        return np.array([e.x, e.y])/self.scale - self.shift

    def on_scroll(self,w,e):
        if e.direction == Gdk.ScrollDirection.DOWN:
            direction = 0.9
        elif e.direction == Gdk.ScrollDirection.UP:
            direction = 1/0.9
        else: return
        self.view_port.zoom(direction, e)
        self.darea.queue_draw()

    def on_motion(self,w,e):
        if e.state & Gdk.ModifierType.BUTTON1_MASK:
            if self.tool == self.move_tool and self.tool_data is not None:
                step = self.tool_data
                step.meta_args = tuple(self.view_port.mouse_coor(e))
                self.env.refresh_steps()
                self.darea.queue_draw()
        if e.state & Gdk.ModifierType.BUTTON2_MASK:
            if self.mb_grasp is None: return
            self.view_port.shift_to_mouse(self.mb_grasp, e)
            self.darea.queue_draw()

    def on_draw(self, wid, cr):

        self.view_port.set_corners(
            self.darea.get_allocated_width(),
            self.darea.get_allocated_height()
        )
        self.view_port.draw(cr, self.env)

    def on_key_press(self,w,e):

        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
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
            self.env.pop_step()
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
            self.save_file(fname)
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

        if e.get_click_count()[1] != 1: return

        coor = self.view_port.mouse_coor(e)

        shift = (e.state & Gdk.ModifierType.SHIFT_MASK)
        if shift and e.button in (1,3):
            obj = self.env.select_obj(coor, self.view_port.scale)
            if obj is not None:
                direction = {1:-1, 3:1}[e.button]
                self.env.swap_priorities(obj, direction)
                self.darea.queue_draw()
            return

        if e.button == 1 and self.tool is not None:
            if e.type != Gdk.EventType.BUTTON_PRESS: return
            self.tool(coor)
            self.darea.queue_draw()
        if e.button == 2:
            self.mb_grasp = coor

    def scripted_tool(self, coor):
        obj = self.env.select_obj(coor, self.view_port.scale)
        if obj is None: self.tool_data = []
        else: self.tool_data.append(obj)

        type_list = tuple(
            self.env.gi_to_type(x)
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

            self.env.add_step(step)

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
        p = self.env.select_movable_obj(coor, self.view_port.scale)
        if p is None:
            self.tool_data = None
            print("No movable point under cursor")
            return
        step_i = self.env.gi_to_step[p]
        step = self.env.steps[step_i]
        if isinstance(step.tool, MovableTool): self.tool_data = step
        else:
            self.tool_data = None
            print("Internal bug: Object is not movable")

    def hide_tool(self, coor):
        TODO_later
        obj = self.select_obj(coor, self.view_port.scale)
        if obj is None: return
        self.constr.hide(obj)
        self.darea.queue_draw()

if __name__ == "__main__":
    win = Drawing()
    Gtk.main()
