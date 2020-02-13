import gi as gtk_import
gtk_import.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from gi.repository.GdkPixbuf import Pixbuf

class ListBoxRowWithData(Gtk.ListBoxRow):
    def __init__(self, data):
        super(Gtk.ListBoxRow, self).__init__()
        self.data = data
        self.add(Gtk.Label(data))

class SelectionEntry(Gtk.Entry):
    def __init__(self, options, *args, **kwargs):
        Gtk.Entry.__init__(self, *args, **kwargs)
        self.on_confirm_hook = None
        self.on_discard_hook = None
        self.on_focus_hook = None
        self.put_focus_away = None

        self.connect("activate", self.on_activate)
        self.connect("focus-in-event", self.on_focus_in)
        self.connect("focus-out-event", self.on_focus_out)
        self.connect("key-press-event", self.on_key_press)
        self.set_options(options)
        self._last_text = ""
        self._focus_out_mode = 0

    def set_options(self, options):
        self.options = list(options)
        self.options_s = set(options)
        liststore = Gtk.ListStore(str)
        self.completion = Gtk.EntryCompletion()
        self.set_completion(self.completion)
        self.completion.set_text_column(0)
        self.completion.set_model(liststore)
        prefixes = set()
        for option in options:
            liststore.append([option])
            for i in range(len(option)+1):
                prefixes.add(option[:i])

        def match_func(completion, key_string, it, data):
            model = completion.get_model()
            modelstr = model[it][0]

            if key_string in prefixes: # there are available completions
                return modelstr.startswith(key_string)
            else: # search more generally
                return key_string in modelstr

        self.completion.set_match_func(match_func, None)
        self.completion.set_inline_completion(True)
        self.completion.set_popup_single_match(True)
        self.completion.connect("match-selected", self.on_completion_match)

    def on_completion_match(self, completion, model, it):
        self.set_text(model[it][0])
        self.activate()
        return True

    def on_activate(self, *args):
        print("activate")
        text = self.get_text()
        if text not in self.options_s: return
        self.unselect(2)
        if self.on_confirm_hook is not None:
            self.on_confirm_hook(text)

    def on_focus_in(self, *args):
        print("focus in event")
        self._last_text = self.get_text()
        if self.on_focus_hook is not None:
            self.on_focus_hook()
    def on_focus_out(self, *args):
        print("focus out event", self._focus_out_mode)
        self.select_region(0,0)
        if self._focus_out_mode != 2:
            self.set_text(self._last_text)
        if self._focus_out_mode == 0:
            if self.on_discard_hook is not None:
                self.on_discard_hook()
        self._focus_out_mode = 0

    def on_key_press(self,w,e):
        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name == "Escape":
            self.unselect()
            return True
        elif keyval_name == "Tab":
            bounds = self.get_selection_bounds()
            if bounds:
                a,b = bounds
                self.select_region(b,b)
            else: self.completion.complete()
            return True
        return False

    def select(self):
        if not self.is_focus():
            self.grab_focus()
            return True
        else: return False
    def unselect(self, mode = 0):
        self._focus_out_mode = mode
        if self.is_focus():
            self._use_out_hook = True
            self.put_focus_away()
            return True
        return False
    def get_current_option(self):
        text = self.get_text()
        if text in self.options_s: return text
        else: return None

class Drawing(Gtk.Window):

    def bind_accelerator(self, widget, accelerator):
        key, mod = Gtk.accelerator_parse(accelerator)
        widget.add_accelerator("activate", self.accelerators,
                               key, mod, Gtk.AccelFlags.VISIBLE)

    def make_toolbar(self, menu_items):
        #vbox = Gtk.VBox()
        #toolbox = Gtk.FlowBox()
        #toolbox.set_valign(Gtk.Align.START)
        #toolbox.set_selection_mode(Gtk.SelectionMode.NONE)
        toolbar = Gtk.HBox()

        menu_button = Gtk.MenuButton()
        toolbar.pack_start(menu_button, False, False, 0)

        menu = Gtk.Menu()
        menu_button.set_popup(menu)
        def f_capsule(action):
            def gtk_action(widget):
                action()
            return gtk_action
        for label, action, accel in menu_items:
            item = Gtk.MenuItem.new_with_label(label)
            menu.append(item)
            item.connect("activate", f_capsule(action))
            if accel is not None:
                self.bind_accelerator(item, accel)
            item.show()

        tools = Gtk.HBox()
        toolbar.pack_end(tools, False, False, 0)

        icons = [
            "point",
            "line", "perpline",
            "circle", "circumcircle",
            "move", "hide", "reason",
        ]
        first_button = None
        self.tool_to_button = dict()
        for icon_name in icons:
            #pixbuf = Gtk.IconTheme.get_default().load_icon(icon_name, 32, 0)
            if first_button is None:
                button = Gtk.RadioToolButton()
                first_button = button
            else: button = Gtk.RadioToolButton.new_from_widget(first_button)
            icon = Gtk.Image.new_from_file("images/icons/{}.png".format(icon_name))
            button.set_icon_widget(icon)
            button.set_tooltip_text(icon_name)
            button.set_property('can-focus', False)
            def tool_button_click(button, name):
                if not button.get_active(): return
                self.change_tool(name)
                self.entry.unselect(1)
            button.connect("toggled", tool_button_click, icon_name)
            self.tool_to_button[icon_name] = button

            tools.pack_start(button, False, False, 0)

        self.other_tool_button = Gtk.RadioToolButton.new_from_widget(first_button)
        self.other_tool_button.set_property('can-focus', False)
        self.other_tool_button.set_icon_name("view-more")
        def other_tool_button_click(button):
            if not button.get_active(): return
            name = self.entry.get_current_option()
            if name is not None: self.change_tool(name)
            else: self.entry.select()
        self.other_tool_button.connect("toggled", other_tool_button_click)
        tools.pack_start(self.other_tool_button, False, False, 0)
        self.entry = SelectionEntry(self.available_tool_names)
        tools.pack_start(self.entry, False, False, 0)

        self.gtool = "point"
        def entry_confirm(name):
            print("CONFIRM")
            self.change_tool(name)
        def entry_focus():
            print("FOCUS", self.gtool)
            if self.gtool is not None: self.pre_entry_tool = self.gtool
            self.other_tool_button.set_active(True)
            self.change_tool(None)
        def entry_discard():
            print("DISCARD", self.pre_entry_tool)
            self.select_tool_button(self.pre_entry_tool)
        self.entry.on_confirm_hook = entry_confirm
        self.entry.on_focus_hook = entry_focus
        self.entry.on_discard_hook = entry_discard

        return toolbar

    def select_tool_button(self, tool):
        if tool is None: return
        button = self.tool_to_button.get(self.pre_entry_tool, None)
        self.change_tool(tool)
        if button is None:
            self.entry.set_text(tool)
            self.other_tool_button.set_active(True)
        else:
            button.set_active(True)

    
    def __init__(self):
        super(Drawing, self).__init__()

        self.accelerators = Gtk.AccelGroup()
        self.add_accel_group(self.accelerators)

        from basic_tools import load_tools
        from gtool_general import GToolDict

        imported_tools = load_tools("macros.gl")
        general_tools = GToolDict(imported_tools.tool_dict)
        tool_names = sorted(general_tools.name_to_prefixes.keys())

        self.available_tool_names = sorted(tool_names)

        self.resize(800, 600)
        #hbox = Gtk.HPaned()
        vbox = Gtk.VBox()
        def open_f(): print("OPEN")
        def save_f(): print("SAVE")
        def save_as_f(): print("SAVE AS")
        menu_items = (
            ("Open...",    open_f,        "<Control>o"),
            ("Save",       save_f,        "<Control>s"),
            ("Save as...", save_as_f,     "<Control><Shift>s"),
            ("Quit...",    Gtk.main_quit, "<Control>q"),
        )
        vbox.pack_start(self.make_toolbar(menu_items), False, False, 0)

        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_property('can-focus', True)
        self.entry.put_focus_away = self.darea.grab_focus
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
        if keyval_name == "Return":
            if self.entry.select(): return True
        else:
            #print(keyval_name)
            pass

    def change_tool(self, tool_name):
        print("Change tool:", tool_name)
        self.gtool = tool_name

if __name__ == "__main__":
    win = Drawing()
    Gtk.main()
