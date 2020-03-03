import gi as gtk_import
gtk_import.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

class VarLabel(Gtk.Label):
    def __init__(self, env, gi):
        Gtk.Label.__init__(self)
        self.env = env
        self.vis = env.vis
        self.gi = gi
        self.selected = None
        self.defined = None
        self.name = env.gi_to_name[gi]
        self.update()

    def update(self):
        li = self.vis.gi_to_li(self.gi)
        defined = li is not None
        selected = li in self.vis.obj_is_selected
        name = self.env.gi_to_name[self.gi]
        if selected is self.selected\
           and defined is self.defined\
           and name is self.name:
            return
        self.selected = selected
        self.defined = defined
        self.name = name
        markup = GLib.markup_escape_text(name)
        if selected: markup = "<span bgcolor='#00FFFF'>"+markup+"</span>"
        elif not defined:
            markup = "<span fgcolor='#777777'>"+markup+"</span>"
        self.set_markup(markup)

class StepMainLabel(Gtk.Label):
    def __init__(self, env, step):
        Gtk.Label.__init__(self)
        self.env = env
        self.step = step
        self.success = None
        self.update()

    def update(self):
        success = self.step.success
        if success is self.success: return
        self.success = success
        markup = GLib.markup_escape_text("<- "+self.step.tool.name)
        if not success:
            markup = "<span fgcolor='#777777'>"+markup+"</span>"
        self.set_markup(markup)

class StepListRow(Gtk.ListBoxRow):
    def __init__(self, step, env):
        Gtk.ListBoxRow.__init__(self)
        self.step = step
        self.env = env
        step.gui_row = self
        self.hbox = Gtk.HBox()
        self.add(self.hbox)

        self.output_widgets = self.make_var_widgets(self.step.local_outputs)
        self.label = StepMainLabel(env, step)
        self.meta_widget = Gtk.Label(self.get_meta_str())
        self.arg_widgets = self.make_var_widgets(self.step.local_args)

        for w in self.output_widgets:
            self.hbox.pack_start(w, False, False, 3)
        self.hbox.pack_start(self.label, False, False, 0)
        self.hbox.pack_start(self.meta_widget, False, False, 0)
        for w in self.arg_widgets:
            self.hbox.pack_start(w, False, False, 3)

    def update_meta(self):
        self.meta_widget.set_text(self.get_meta_str())

    def make_var_widgets(self, var_list):
        return [VarLabel(self.env, gi) for gi in var_list]
    def get_meta_str(self):
        res = ' '
        for meta_arg in self.step.meta_args:
            if isinstance(meta_arg, float):
                res += "{:.3}".format(meta_arg)
            else: res += str(meta_arg)
            res += ' '
        return res

    def update_selected(self):
        self.label.update()
        for w in self.output_widgets: w.update()
        for w in self.arg_widgets: w.update()

class ListRowSeparator(Gtk.ListBoxRow):
    def __init__(self):
        Gtk.ListBoxRow.__init__(self)
        #self.set_activatable(False)
        self.set_selectable(False)
        self.add(Gtk.HSeparator())
        self.show_all()
    def update_meta(self):
        pass
    def update_selected(self):
        pass

class StepList(Gtk.ScrolledWindow):
    def __init__(self, env):
        super(StepList, self).__init__()
        self.listbox = Gtk.ListBox()
        self.add(self.listbox)
        self.insert_position = 0
        #self.listbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)
        #self.listbox.set_activate_on_single_click(False)
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)

        env.add_step_hook = self.add_step
        env.remove_step_hook = self.remove_step
        env.reload_steps_hook = self.load_steps
        env.update_meta_hook = self.update_meta
        env.vis.update_selected_hook = self.update_selected
        #for i in range(20):
        #    label = Gtk.Label("An item number %d" % i, xalign=0)
        #    self.listbox.add(label)
        self.env = env
        self.load_steps()

    def load_steps(self):
        for row in self.listbox.get_children(): 
            self.listbox.remove(row)
        self.insert_position = 0

        steps = self.env.steps
        goals = self.env.goals
        use_sep = goals is not None
        if use_sep:
            proof = self.env.steps[self.env.min_steps:]
            steps = self.env.steps[:self.env.min_steps]

        for step in steps:
            self.add_step(step)

        if use_sep:
            self.add_separator()
            if proof:
                for step in proof:
                    self.add_step(step)
            insert_pos = self.insert_position
            self.add_separator()
            for step in goals:
                self.add_step(step)
            self.insert_position = insert_pos

    def add_separator(self):
        self.listbox.insert(ListRowSeparator(), self.insert_position)
        self.insert_position += 1

    def add_step(self, step):
        row = StepListRow(step, self.env)
        row.show_all()
        self.listbox.insert(row, self.insert_position)
        self.insert_position += 1

    def update_meta(self, step):
        step.gui_row.update_meta()

    def remove_step(self, step):
        self.listbox.remove(step.gui_row)
        step.gui_row = None
        self.insert_position -= 1

    def update_selected(self):
        for row in self.listbox.get_children():
            row.update_selected()
