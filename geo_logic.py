#!/usr/bin/python3

import gi as gtk_import
gtk_import.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
import numpy as np
from geo_object import *
from parse import Parser, type_to_c
import primitive_pred
from collections import defaultdict
from tool_step import ToolStep, proof_checker
from file_chooser import select_file_open, select_file_save, add_svg_filters
from stop_watch import print_times, StopWatch
from itertools import islice
from viewport import Viewport
from graphical_env import GraphicalEnv
from movable_tools import MovableTool
from basic_tools import load_tools, ImportedTools
from gtool import ObjSelector, GTool, GToolMove, GToolHide
from gtool_general import GToolDict
from gtool_label import GToolLabel
from gtool_logic import GToolReason
from gtool_constr import ComboPoint, ComboLine, ComboPerpLine, ComboCircle, ComboCircumCircle
from toolbar import ToolBar
from step_list import StepList
from logical_core import LogicalCore

class GeoLogic(Gtk.Window):

    def __init__(self):
        super(GeoLogic, self).__init__()

        self.imported_tools = load_tools("macros.gl")
        self.env = GraphicalEnv(self.imported_tools)
        self.vis = self.env.vis
        self.general_tools = GToolDict(self.imported_tools.tool_dict)
        self.keyboard_capture = None

        menu_items = (
            ("Undo", self.undo,     "<Control>z"),
            ("Redo", self.redo,     "<Control><Shift>z"),
            ("Reset", self.restart, "<Control>n"),
            ("Open...", self.load,  "<Control>o"),
            ("Save", self.save,     "<Control>s"),
            ("Save as...", self.save_as, "<Control><Shift>s"),
            ("Export SVG...", self.export_svg, "<Control><Shift>e"),
            ("Quit", self.on_exit,  "<Control>q"),
        )
        gtools = (
            ComboPoint(),
            ComboLine(), ComboPerpLine(),
            ComboCircle(), ComboCircumCircle(),
            GToolMove(), GToolHide(), GToolLabel(),
            GToolReason(),
        )
        self.key_to_gtool = dict(
            (gtool.get_key_shortcut(), gtool)
            for gtool in gtools
        )

        vbox = Gtk.VBox()
        self.add(vbox)

        self.toolbar = ToolBar(menu_items, gtools, self.general_tools)
        vbox.pack_start(self.toolbar, False, False, 0)

        hpaned = Gtk.HPaned()
        vbox.add(hpaned)
        self.step_list = StepList(self.env)
        hpaned.pack1(self.step_list, False, True)

        self.viewport = Viewport(self.env, self)
        self.viewport.set_tool(ComboPoint())
        hpaned.pack2(self.viewport.darea, True, False)
        hpaned.set_position(250)

        self.viewport.click_hook = self.toolbar.entry.unselect
        self.toolbar.set_entry_unselect(self.viewport.darea.grab_focus)
        self.toolbar.change_tool_hook = self.viewport.set_tool
        self.add_accel_group(self.toolbar.accelerators)

        def update_progress_bar(done, size):
            if size == 0: self.progress_bar.set_fraction(0)
            else: self.progress_bar.set_fraction(done / size)
            return False
        def update_progress_bar_idle(done, size):
            GLib.idle_add(update_progress_bar, done, size)
        proof_checker.paralelize(progress_hook = update_progress_bar_idle)
        
        self.progress_bar = Gtk.ProgressBar(show_text=False)
        vbox.pack_end(self.progress_bar, False, False, 0)

        self.connect("key-press-event", self.on_key_press)
        self.connect("key-release-event", self.on_key_release)
        self.connect("delete-event", self.on_exit)
        self.resize(1000, 600)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_events(Gdk.EventMask.KEY_PRESS_MASK |
                        Gdk.EventMask.KEY_RELEASE_MASK)

        self.show_all()

        self.update_title(None)

    # changes the default filename for saving and the title of the window
    def update_title(self, fname):
        self.default_fname = fname
        title = "GeoLogic"
        if fname is not None:
            title = "{} -- {}".format(title, fname.split('/')[-1])
        self.set_title(title)
        
    def reset_view(self):
        if self.vis.view_changed:
            self.viewport.gtool.reset()
            self.viewport.darea.queue_draw()

    def undo(self):
        proof_checker.disable()
        self.env.pop_step()
        self.reset_view()
        proof_checker.enable()
    def redo(self):
        self.env.redo()
        self.reset_view()
    def restart(self):
        #print("RESTART")
        self.update_title(None)
        self.viewport.reset_tool()
        self.env.set_steps((), ())
        self.viewport.reset_zoom()
        self.reset_view()
    def load(self):
        fname = select_file_open(self)
        self.load_file(fname)
    def save(self):
        fname = self.default_fname
        if fname is None: fname = select_file_save(self)
        self.save_file(fname)
    def save_as(self):
        fname = select_file_save(self)
        self.save_file(fname)
    def export_svg(self):
        fname = select_file_save(
            self, "Export SVG", folder = "pictures",
            add_filters = add_svg_filters,
        )
        if fname is not None: self.viewport.export_svg(fname)
    def on_exit(self, *args):
        print_times()
        Gtk.main_quit()

    def load_file(self, fname):
        self.viewport.reset_tool()
        if fname is None: return
        self.update_title(fname)
        parser = Parser(self.imported_tools.tool_dict)
        parser.parse_file(fname, axioms = True)
        loaded_tool = parser.tool_dict['_', ()]
        steps = loaded_tool.assumptions
        names = [
            loaded_tool.var_to_name_proof[x]
            for x in range(len(loaded_tool.var_to_name_proof))
        ]
        if loaded_tool.implications:
            goals, proof = loaded_tool.implications, loaded_tool.proof
        else: goals, proof = None, None
        self.env.set_steps(steps, names = names,
                           goals = goals, proof = proof)

        # hide objects
        visible = set(loaded_tool.result) # old format
        if visible:
            for gi in range(len(self.vis.gi_to_hidden)):
                self.vis.gi_to_hidden[gi] = gi not in visible
        for gi,name in enumerate(names): # new format
            if ("hide__{}".format(name), ()) in parser.tool_dict:
                self.vis.gi_to_hidden[gi] = True

        # set labels
        for gi,name in enumerate(names): # new format
            label_pos_tool = parser.tool_dict.get(("label__{}".format(name), ()), None)
            if label_pos_tool is not None:
                self.vis.gi_label_show[gi] = True
                logic = LogicalCore(basic_tools = self.imported_tools)
                pos_l = label_pos_tool.run((), (), logic, 0)
                pos_n = [logic.num_model[x] for x in pos_l]
                t = self.vis.gi_to_type(gi)
                if t == Point:
                    point, = pos_n
                    position = point.a
                    print(position)
                elif t == Line:
                    position = tuple(d.x for d in pos_n)
                elif t == Circle:
                    ang, offset = pos_n
                    position = ang.data*2, offset.x
                else:
                    print("Warning: save label: unexpected type {} of {}".format(t, name))
                    continue
                self.vis.gi_label_position[gi] = position

        self.vis.refresh()

        # viewport zoom and position
        view_data_tool = parser.tool_dict.get(('view__data', ()), None)

        if view_data_tool is None:
            self.viewport.set_zoom((375, 277), 1)
        else:
            logic = LogicalCore(basic_tools = self.imported_tools)
            anchor_l, zoom_l = view_data_tool.run((), (), logic, 0)
            anchor = logic.num_model[anchor_l].a
            zoom = logic.num_model[zoom_l].x
            self.viewport.set_zoom(anchor, zoom)

        self.reset_view()
    def save_file(self, fname):
        if fname is None: return
        print("saving to '{}'".format(fname))
        self.update_title(fname)
        with open(fname, 'w') as f:
            #visible = [
            #    "{}:{}".format(
            #        self.env.gi_to_name[gi],
            #        type_to_c[self.vis.gi_to_type(gi)]
            #    )
            #    for gi,hidden in enumerate(self.vis.gi_to_hidden)
            #    if not hidden
            #]
            #f.write('_ -> {}\n'.format(' '.join(sorted(visible))))
            f.write('_ ->\n')

            def write_step(step):
                tokens = [self.env.gi_to_name[x] for x in step.local_outputs]
                tokens.append('<-')
                tokens.append(step.tool.name)
                tokens.extend(map(str, step.hyper_params))
                tokens.extend(self.env.gi_to_name[x] for x in step.local_args)
                f.write('  '+' '.join(tokens)+'\n')

            if self.env.goals is None:
                for step in self.env.steps: write_step(step)
            else:
                for step in self.env.steps[:self.env.min_steps]: write_step(step)
                f.write('  THEN\n')
                for step in self.env.goals: write_step(step)
                f.write('  PROOF\n')
                for step in self.env.steps[self.env.min_steps:]: write_step(step)

            # hidden objects and labels
            f.write("\n")
            for gi, (name, hidden, label_show, label_pos) in enumerate(zip(
                    self.env.gi_to_name, self.vis.gi_to_hidden, self.vis.gi_label_show, self.vis.gi_label_position)):
                if hidden: f.write("hide__{} ->\n".format(name))
                if label_show:
                    t = self.vis.gi_to_type(gi)
                    if t == Point:
                        label_attrs = [('pos', 'P', 'free_point', tuple(map(float, label_pos)))]
                    elif t == Line:
                        pos, offset = label_pos
                        label_attrs = [
                            ('pos', 'D', 'custom_ratio', (float(pos), 0.)),
                            ('offset', 'D', 'custom_ratio', (float(offset), 0.)),
                        ]
                    elif t == Circle:
                        direction, offset = label_pos
                        label_attrs = [
                            ('direction', 'A', 'custom_angle', (float(direction/2),)),
                            ('offset', 'D', 'custom_ratio', (float(offset), 0.)),
                        ]
                    else:
                        print("Warning: save label: unexpected type {} of {}".format(t, name))
                        continue
                    label_attr_names = [
                        "{}:{}".format(attr_name, t) for attr_name, t, _, _ in label_attrs
                    ]
                    f.write("label__{} -> {}\n".format(name, ' '.join(label_attr_names)))
                    for attr_name, _, attr_constructor, attr_values in label_attrs:
                        f.write("  {} <- {} {}\n".format(attr_name, attr_constructor,
                                                         ' '.join(map(str, attr_values))))

            # writing current zoom and position
            f.write("\n")
            f.write("view__data -> anchor:P zoom:D\n")
            f.write("  anchor <- free_point {} {}\n".format(*self.viewport.view_center))
            f.write("  zoom <- custom_ratio {} 0.\n".format(self.viewport.scale))

        self.reset_view()

    def on_key_press(self,w,e):

        if self.keyboard_capture is not None:
            return self.keyboard_capture(e)

        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        modifier = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK
        if e.state & modifier: return False
        if self.toolbar.entry.is_focus(): return

        if keyval_name == "Return":
            self.toolbar.entry.select()
            return True
        elif keyval_name in self.key_to_gtool:
            gtool = self.key_to_gtool[keyval_name]
            self.toolbar.select_tool_button(gtool)
            self.reset_view()
            return True
        elif keyval_name.startswith("Shift"):
            self.viewport.update_shift_pressed(True)
            self.viewport.darea.queue_draw()
            return False
        else:
            #print(keyval_name)
            return False

    def on_key_release(self,w,e):
        keyval_name = Gdk.keyval_name(e.keyval)
        if keyval_name.startswith("Shift"):
            self.viewport.update_shift_pressed(False)
            self.viewport.darea.queue_draw()

if __name__ == "__main__":
    win = GeoLogic()
    Gtk.main()
