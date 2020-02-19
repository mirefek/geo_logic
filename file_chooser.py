import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
import os

def add_svg_filters(dialog):
    filter_gl = Gtk.FileFilter()
    filter_gl.set_name("SVG Images")
    filter_gl.add_mime_type("image/svg+xml")
    filter_gl.add_pattern("*.svg")
    dialog.add_filter(filter_gl)

    filter_any = Gtk.FileFilter()
    filter_any.set_name("Any files")
    filter_any.add_pattern("*")
    dialog.add_filter(filter_any)

def add_gl_filters(dialog):
    filter_gl = Gtk.FileFilter()
    filter_gl.set_name("GeoLogic Files")
    filter_gl.add_mime_type("text/geo_logic")
    filter_gl.add_pattern("*.gl")
    dialog.add_filter(filter_gl)

    filter_any = Gtk.FileFilter()
    filter_any.set_name("Any files")
    filter_any.add_pattern("*")
    dialog.add_filter(filter_any)

def select_file_open(win, add_filters = add_gl_filters):
    dialog = Gtk.FileChooserDialog("Open a file", win,
        Gtk.FileChooserAction.OPEN,
        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
         Gtk.STOCK_OPEN, Gtk.ResponseType.OK))
    dialog.set_current_folder("saved")

    add_filters(dialog)

    response = dialog.run()

    if response == Gtk.ResponseType.OK:
        res = dialog.get_filename()
    else: res = None

    dialog.destroy()
    return res

class DialogSaveFile(Gtk.Dialog):
    def __init__(self, parent, db):
        Gtk.Dialog.__init__(self, "Confirm overwrite", parent, 0,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
             Gtk.STOCK_OK, Gtk.ResponseType.OK))
        self.box = self.get_content_area()
        self.label = Gtk.Label("The file `" + db + "` exists.\nDo you want it to be overwritten?")
        self.box.add(self.label)
        self.show_all()

def select_file_save(win, win_title = "Save file", folder = "saved", add_filters = add_gl_filters):
    dialog = Gtk.FileChooserDialog(win_title, win,
        Gtk.FileChooserAction.SAVE,
        (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
         Gtk.STOCK_SAVE, Gtk.ResponseType.OK))
    add_filters(dialog)
    dialog.set_current_folder(folder)

    while True:

        response = dialog.run()

        if response == Gtk.ResponseType.OK:
            res = dialog.get_filename()
        else:
            res = None
            break

        cansave = True
        if os.path.exists(dialog.get_filename()):
            dialog2 = DialogSaveFile(dialog, dialog.get_filename())  # ask to confirm overwrite
            response = dialog2.run()
            if response == Gtk.ResponseType.OK:
                dialog2.destroy()
            else:
                cansave = False
                dialog2.destroy()

        if cansave: break

    dialog.destroy()
    return res
