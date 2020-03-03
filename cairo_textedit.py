import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GObject
import cairo
import numpy as np
from label_visualiser import LabelVisualiser

class Drawing(Gtk.Window):
    def __init__(self):
        super(Drawing, self).__init__()    

        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                              Gdk.EventMask.KEY_PRESS_MASK
        )
        self.add(self.darea)

        self.darea.connect("button-press-event", self.on_button_press)
        self.connect("key-press-event", self.on_key_press)

        self.text = 'A_1_Ba_c_X'
        self.text_coor = None
        self.cursor = None

        self.set_title("Drawing")
        self.resize(600, 400)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", Gtk.main_quit)
        self.show_all()

        self.label_vis = LabelVisualiser()

        self.timer = None
        self.circle = None

    def on_draw(self, wid, cr):

        size = self.get_size()
        cr.rectangle(0, 0, size[0], size[1])
        cr.set_source_rgb(1, 1, 1)
        cr.fill()

        cr.translate(200, 100)

        cr.select_font_face('serif', cairo.FONT_SLANT_ITALIC)
        if self.cursor is None:
            texts, subscripts, extents = self.label_vis.parse(cr, self.text)
            width, height = extents[2:4]
            cr.rectangle(-width/2,-height/2,width,height)
            cr.set_source_rgb(0, 1, 1)
            cr.fill()
            cr.set_source_rgb(0, 0, 0)
            self.label_vis.show_center(cr, texts, subscripts, extents)
            self.text_coor = self.label_vis.get_center_start(extents)
        else:
            cr.set_source_rgb(0, 0, 0)
            self.label_vis.show_edit(cr, self.text, self.cursor, self.text_coor)

    def on_key_press(self,w,e):

        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        print(keyval_name)
        #if keyval_name == 'p':

        if keyval_name.startswith("KP_"):
            keyval_name = keyval_name[3:]
            print("  [kp]", keyval_name)

        if keyval_name == "Escape":
            Gtk.main_quit()
        elif keyval_name == "Left":
            if self.cursor is None or self.cursor < 2:
                self.cursor = 0
            else: self.cursor -= 1
        elif keyval_name == "Return":
            print("Confirm:", self.text)
            self.cursor = None
        elif keyval_name == "Right":
            if self.cursor is None or self.cursor >= len(self.text):
                self.cursor = len(self.text)
            else: self.cursor += 1
        elif keyval_name in ("BackSpace", "Delete"):
            if self.cursor is None:
                self.cursor = 0
                self.text = ""
            else:
                if keyval_name == "BackSpace":
                    if self.cursor == 0: return True
                    else: self.cursor -= 1
                if self.cursor == len(self.text): return True
                print(self.text)
                self.text = self.text[:self.cursor]+self.text[self.cursor+1:]
                print("--", self.text)
        elif len(e.string) == 1 and ord(e.string) >= ord(' '):
            #print(ord(e.string))
            if self.cursor is None:
                if e.string.islower() and self.text[:1].isupper():
                    self.text = e.string.upper()
                else: self.text = e.string
                self.cursor = 1
            else:
                self.text = self.text[:self.cursor] + e.string + self.text[self.cursor:]
                self.cursor += 1
        else:
            return False

        self.darea.queue_draw()
        return True

    def on_button_press(self, w, e):

        #if e.button != 1: return
        if e.type != Gdk.EventType.BUTTON_PRESS: return

        self.darea.queue_draw()

    def on_button_release(self, w, e):
        
        if e.type != Gdk.EventType.BUTTON_RELEASE: return

        self.tool.on_button_release(e.x, e.y)
        self.darea.queue_draw()


if __name__ == "__main__":
    win = Drawing()
    Gtk.main()
