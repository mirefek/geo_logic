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
from file_chooser import select_file_open, select_file_save
from stop_watch import print_times, StopWatch
from itertools import islice
from viewport import Viewport
from graphical_env import GraphicalEnv
from movable_tools import MovableTool
from basic_tools import load_tools, ImportedTools
from gtool_general import GToolDict
from gtool import ObjSelector, GTool, GToolMove, GToolHide
from gtool_logic import GToolReason
from gtool_constr import ComboPoint, ComboLine, ComboPerpLine, ComboCircle, ComboCircumCircle
from toolbar import ToolBar

class GeoLogic(Gtk.Window):

    def __init__(self):

        self.imported_tools = load_tools("macros.gl")
        self.env = GraphicalEnv(self.imported_tools)
        self.general_tools = GToolDict(self.imported_tools.tool_dict)

        menu_items = (
            ("Undo", self.undo,     "<Control>z"),
            ("Redo", self.redo,     "<Control><Shift>z"),
            ("Reset", self.restart, "<Control>n"),
            ("Open...", self.load,  "<Control>o"),
            ("Save", self.save,     "<Control>s"),
            ("Save as...", self.save_as, "<Control><Shift>s"),
            ("Quit", self.on_exit,  "<Control>q"),
        )
        gtools = (
            ComboPoint(),
            ComboLine(), ComboPerpLine(),
            ComboCircle(), ComboCircumCircle(),
            GToolMove(), GToolHide(), GToolReason(), 
        )
        self.key_to_gtool = dict(
            (gtool.get_key_shortcut(), gtool)
            for gtool in gtools
        )

        super(GeoLogic, self).__init__()
        vbox = Gtk.VBox()
        self.add(vbox)

        self.toolbar = ToolBar(menu_items, gtools, self.general_tools)
        vbox.pack_start(self.toolbar, False, False, 0)

        self.viewport = Viewport(self.env)
        self.viewport.set_tool(ComboPoint())
        vbox.add(self.viewport.darea)

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


        self.default_fname = None


    def reset_view(self):
        if self.env.view_changed:
            self.viewport.gtool.reset()
            self.viewport.darea.queue_draw()

    def undo(self):
        self.env.pop_step()
        self.reset_view()
    def redo(self):
        self.env.redo()
        self.reset_view()
    def restart(self):
        print("RESTART")
        self.default_fname = None
        self.env.set_steps(())
        self.reset_view()
    def load(self):
        fname = select_file_open(self)
        self.load_file(fname)
    def save(self):
        fname = select_file_save(self)
        self.save_file(fname)
    def save_as(self):
        fname = self.default_fname
        if fname is None: fname = select_file_save(self)
        self.save_file(fname)
    def on_exit(self, *args):
        print_times()
        Gtk.main_quit()

    def load_file(self, fname):
        if fname is None: return
        self.default_fname = fname
        parser = Parser(self.imported_tools.tool_dict)
        parser.parse_file(fname, axioms = False)
        loaded_tool = parser.tool_dict['_', ()]
        visible = set(loaded_tool.result)
        if not visible: visible = None
        self.env.set_steps(loaded_tool.assumptions, visible = visible)
        self.reset_view()
    def save_file(self, fname):
        if fname is None: return
        print("saving to '{}'".format(fname))
        self.default_fname = fname
        with open(fname, 'w') as f:
            visible = [
                "x{}:{}".format(gi, type_to_c[self.env.gi_to_type(gi)])
                for gi,hidden in enumerate(self.env.gi_to_hidden)
                if not hidden
            ]
            f.write('_ -> {}\n'.format(' '.join(sorted(visible))))
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
        self.reset_view()

    def on_key_press(self,w,e):

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
