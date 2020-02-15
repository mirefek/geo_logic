import gi as gtk_import
gtk_import.require_version("Gtk", "3.0")
from gi.repository import Gtk

class StepList(Gtk.ScrolledWindow):
    def __init__(self, env):
        super(StepList, self).__init__()
        self.listbox = Gtk.ListBox()
        self.add(self.listbox)
        #self.listbox.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        env.add_step_hook = self.add_step
        env.remove_step_hook = self.remove_step
        env.reload_steps_hook = self.load_steps
        env.update_step_hook = self.update_step
        #for i in range(20):
        #    label = Gtk.Label("An item number %d" % i, xalign=0)
        #    self.listbox.add(label)
        self.env = env
        self.load_steps(self.env.steps)

    def load_steps(self, steps):
        for row in self.listbox.get_children(): 
            self.listbox.remove(row)
        for step in steps:
            self.add_step(step)

    def add_step(self, step):
        row = Gtk.Label(self.get_step_str(step), xalign=0)
        self.listbox.add(row)
        row.show()

    def update_step(self, i, step):
        #row = self.listbox.get_row_at_index(i)
        #print(row.get_child)
        #row.get_child.set_text(self.get_step_text(step))
        print("update")

    def remove_step(self, i):
        row = self.listbox.get_row_at_index(i)
        self.listbox.remove(row)

    def get_step_str(self, step):
        tokens = [step.tool.name]
        for meta_arg in step.meta_args:
            if isinstance(meta_arg, float):
                tokens.append("{:.3}".format(meta_arg))
            else: tokens.append(str(meta_arg))
        tokens.extend('x{}'.format(x) for x in step.local_args)
        return ' '.join(tokens)
