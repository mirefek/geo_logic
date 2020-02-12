import gi as gtk_import
gtk_import.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from gi.repository.GdkPixbuf import Pixbuf

class ListBoxRowWithData(Gtk.ListBoxRow):
    def __init__(self, data):
        super(Gtk.ListBoxRow, self).__init__()
        self.data = data
        self.add(Gtk.Label(data))

class Drawing(Gtk.Window):

    def make_toolbar(self):
        #vbox = Gtk.VBox()
        #toolbox = Gtk.FlowBox()
        #toolbox.set_valign(Gtk.Align.START)
        #toolbox.set_selection_mode(Gtk.SelectionMode.NONE)
        toolbar = Gtk.HBox()

        icons = [
            "point",
            "line", "perpline",
            "circle", "circumcircle",
            "move", "hide", "derive",
        ]
        first_button = None
        for icon_name in icons:
            #pixbuf = Gtk.IconTheme.get_default().load_icon(icon_name, 32, 0)
            if first_button is None:
                button = Gtk.RadioToolButton()
                first_button = button
            else: button = Gtk.RadioToolButton.new_from_widget(first_button)
            icon = Gtk.Image.new_from_file("images/icons/{}.png".format(icon_name))
            button.set_icon_widget(icon)
            #button.set_icon_name(icon_name)
            button.set_tooltip_text(icon_name)

            toolbar.pack_start(button, False, False, 0)

        #vbox.pack_start(toolbox, False, False, 0)
        #general_tool_line = Gtk.HBox()
        #vbox.pack_start(general_tool_line, False, False, 0)

        button = Gtk.RadioToolButton.new_from_widget(first_button)
        button.set_icon_name("view-more")
        toolbar.pack_start(button, False, False, 0)
        self.entry = Gtk.Entry()
        toolbar.pack_start(self.entry, False, False, 0)
        self.entry.connect("activate", self.on_activate)

        self.completion = Gtk.EntryCompletion()
        self.entry.set_completion(self.completion)
        self.completion.connect("match-selected", self.on_completion_match)

        liststore = Gtk.ListStore(str)
        self.completion.set_text_column(0)
        self.completion.set_model(liststore)
        tool_prefixes = set()
        for tool_name in self.available_tool_names:
            liststore.append([tool_name])
            for i in range(len(tool_name)+1):
                tool_prefixes.add(tool_name[:i])

        def match_func(completion, key_string, it, data):
            model = completion.get_model()
            # get the completion strings
            modelstr = model[it][0]
            #print("match", key_string, modelstr)
            #print(it)

            # we have only one word typed
            if key_string in tool_prefixes: return modelstr.startswith(key_string)
            else: return key_string in modelstr

        self.completion.set_match_func(match_func, None)
        self.completion.set_inline_completion(True)
        self.completion.set_popup_single_match(True)


        if False:
            scrolled = Gtk.ScrolledWindow()
            scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            vbox.pack_start(scrolled, True, True, 0)

            listbox = Gtk.ListBox()
            scrolled.add(listbox)
            for tool_name in self.available_tool_names:
                listbox.add(ListBoxRowWithData(tool_name))

            def sort_func(row_1, row_2, data, notify_destroy):
                return row_1.data.lower() > row_2.data.lower()

            def filter_func(row, data, notify_destroy):
                return False if row.data == 'Fail' else True

            listbox.set_sort_func(sort_func, None, False)
            listbox.set_filter_func(filter_func, None, False)

        return toolbar

    def __init__(self):
        super(Drawing, self).__init__()

        from basic_tools import load_tools
        from gtool_general import GToolDict

        imported_tools = load_tools("macros.gl")
        general_tools = GToolDict(imported_tools.tool_dict)
        tool_names = sorted(general_tools.name_to_prefixes.keys())

        self.available_tool_names = sorted(tool_names)

        self.resize(600, 400)
        #hbox = Gtk.HPaned()
        vbox = Gtk.VBox()
        vbox.pack_start(self.make_toolbar(), False, False, 0)

        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_property('can-focus', True)
        vbox.pack_start(self.darea, True, True, 0)

        self.add(vbox)
        self.set_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.show_all()

        self.connect("key-press-event", self.on_key_press)

    def on_draw(self, wid, cr):

        w = wid.get_allocated_width()
        h = wid.get_allocated_height()
        cr.rectangle(0,0,w,h)
        cr.set_source_rgb(1,1,1)
        cr.fill()

    def on_key_press(self,w,e):
        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name == "Escape":
            Gtk.main_quit()
        elif keyval_name == "Return":
            #self.entry.activate()
            #self.entry.set_state(Gtk.StateType.FOCUSED)
            if not self.entry.is_focus():
                print("Enter")
                self.entry.grab_focus()
                return True
        else:
            print(keyval_name)

    def on_completion_match(self, completion, model, it):
        print("match:", self.entry.get_text(), model[it][0])
        self.entry.set_text(model[it][0])
        self.entry.activate()
        return True

    def on_activate(self,*args):
        text = self.entry.get_text()
        if text not in self.available_tool_names: return
        self.entry.select_region(0,0)
        print("activate", args)
        #self.entry.unset_state_flags(
        #    Gtk.StateFlags.SELECTED | Gtk.StateFlags.FOCUSED
        #)
        self.darea.grab_focus()

if __name__ == "__main__":
    win = Drawing()
    Gtk.main()
