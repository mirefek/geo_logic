import gi as gtk_import
gtk_import.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from gtool_general import GToolGeneral

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
        #print("activate")
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

class ToolBar(Gtk.HBox):
    def __init__(self, menu_items, gtools, gtool_dict):

        Gtk.HBox.__init__(self)

        self.accelerators = Gtk.AccelGroup()

        self.change_tool_hook = None
        
        ####  Menu
        
        menu_button = Gtk.MenuButton()
        self.pack_start(menu_button, False, False, 0)

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
                key, mod = Gtk.accelerator_parse(accel)
                item.add_accelerator(
                    "activate", self.accelerators,
                    key, mod, Gtk.AccelFlags.VISIBLE
                )
            item.show()

        ####  Tools

        self.toolbox = Gtk.HBox()
        self.pack_end(self.toolbox, False, False, 0)
        self.first_radio = None

        self.tool_to_button = dict()
        for gtool in gtools:
            icon_name = gtool.get_icon_name()
            icon = Gtk.Image.new_from_file(
                "images/icons/{}.png".format(icon_name))
            label = gtool.get_label()
            button = self.add_radio_button(icon, label)
            button.connect("toggled", self.tool_button_click, gtool)
            self.tool_to_button[gtool] = button

        self.other_tool_button = self.add_radio_button(
            "view-more", "Other tool (Enter)")
        self.other_tool_button.connect(
            "toggled", self.other_tool_button_click)
        self.gtool = gtools[0]

        #### Entry

        self.gtool_dict = gtool_dict
        names = sorted(gtool_dict.name_to_prefixes.keys())
        self.entry = SelectionEntry(names)
        self.toolbox.pack_start(self.entry, False, False, 0)

        def entry_confirm(name):
            tool = gtool_dict.make_tool(name)
            self.change_tool(tool)
        def entry_focus():
            if self.gtool is not None: self.pre_entry_tool = self.gtool
            self.other_tool_button.set_active(True)
            self.change_tool(None)
        def entry_discard():
            self.select_tool_button(self.pre_entry_tool)

        self.entry.on_confirm_hook = entry_confirm
        self.entry.on_focus_hook = entry_focus
        self.entry.on_discard_hook = entry_discard

    def add_radio_button(self, icon, label):
        if self.first_radio is None:
            self.first_radio = Gtk.RadioToolButton()
            button = self.first_radio
        else: button = Gtk.RadioToolButton.new_from_widget(self.first_radio)
        if isinstance(icon, str): button.set_icon_name(icon)
        else: button.set_icon_widget(icon)
        button.set_tooltip_text(label)
        self.toolbox.pack_start(button, False, False, 0)
        return button

    def tool_button_click(self, button, tool):
        if not button.get_active(): return
        self.change_tool(tool)
        self.entry.unselect(1)
    def other_tool_button_click(self, button):
        if not button.get_active(): return
        name = self.entry.get_current_option()
        if name is None:
            self.entry.select()
            return

        tool = self.gtool_dict.make_tool(name)
        self.change_tool(tool)

    def set_entry_unselect(self, f):
        self.entry.put_focus_away = f

    def select_tool_button(self, tool):
        if tool is None: return
        if isinstance(tool, GToolGeneral):
            self.entry.set_text(tool.name)
            self.other_tool_button.set_active(True)
        else:
            button = self.tool_to_button.get(tool, None)
            button.set_active(True)
        self.change_tool(tool)

    def change_tool(self, tool):
        self.gtool = tool
        if self.change_tool_hook is not None:
            self.change_tool_hook(tool)
