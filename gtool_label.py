import numpy as np
from geo_object import *
from gtool import GTool
from gi.repository import Gtk, Gdk, GLib

class GToolLabel(GTool):

    icon_name = "label"
    key_shortcut = 'a'
    label = "Label Tool"

    def __init__(self, *args, **kwargs):
        GTool.__init__(self, *args, **kwargs)
        self.label_edit = None
        self.obj_edit = None
        self.no_cancel = False

    def update_basic(self, coor):
        obj,objn = self.select_pcl(coor)
        if obj is not None:
            #self.hl_select((obj, "label"))
            prev_hidden = not self.vis.gi_label_show[obj]
            if prev_hidden:
                self.confirm = self.label_activate, obj, objn, coor
            else: self.confirm = self.label_hide, obj
            self.drag = self.label_drag, obj, objn, prev_hidden

    # mouse movement with edited label (with cursor)
    def update_edited(self, coor):
        self.confirm = self.confirm_edit
        obj = self.obj_edit
        nobj = self.vis.gi_to_num(self.obj_edit)
        if nobj.dist_from(coor) < 2*self.find_radius:
            self.drag = self.label_drag, obj, nobj

    def label_hide(self, obj):
        self.vis.gi_label_show[obj] = False
        self.vis.visible_export()

    # unhide and select, capture keyboard for editing the current label
    def label_activate(self, obj, objn, coor = None):
        if self.obj_edit is not None and obj == self.obj_edit:
            self.on_reset()
            return
        self.on_reset()

        self.vis.gi_label_show[obj] = False
        self.vis.view_changed = True
        self.no_cancel = True
        self.label_edit = [
            None, self.env.gi_to_name[obj],
        ]
        self.obj_edit = obj
        position = self.vis.get_label_position(obj)
        if isinstance(objn, Circle):
            direction, offset = position
            label_coor = objn.c + objn.r * vector_of_direction(direction)
            c1, c2 = self.viewport.corners
            if ((label_coor <= c1).any() or (label_coor >= c2).any())\
               and not eps_identical(objn.c, coor):
                direction = vector_direction(coor - objn.c)
                position = direction, offset
                self.vis.gi_label_position[obj] = position

        self.viewport.edited_label = [
            self.env.gi_to_name[obj], objn,
            position,
            self.label_edit
        ]
        self.viewport.app.keyboard_capture = self.on_key_edit
        #self.vis.gi_label_show[obj] = not self.vis.gi_label_show[obj]
        self.viewport.darea.queue_draw()

    ## Properties active during editing -- cursor position and the current text
        
    @property
    def cursor(self):
        return self.label_edit[0]
    @cursor.setter
    def cursor(self, value):
        if self.cursor is None: self.edit_start()
        self.label_edit[0] = value
    @property
    def new_text(self):
        return self.label_edit[1]
    @new_text.setter
    def new_text(self, value):
        self.label_edit[1] = value

    # when starting writing, or moving cursor
    def edit_start(self):
        self.update = self.update_edited

        # highlight only the edited object
        self.hl_selected.ini = [(self.obj_edit, True)]
        self._hl_load()
        self._hl_update()

    # key event handler
    def on_key_edit(self, e):
        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name.startswith("KP_"):
            keyval_name = keyval_name[3:]
        if keyval_name == "Escape":
            self.reset()
            return True
        elif keyval_name == "Left":
            if self.cursor is None or self.cursor < 2:
                self.cursor = 0
            else: self.cursor = self.cursor - 1
        elif keyval_name == "Return":
            self.confirm_edit()
            return True
        elif keyval_name == "Right":
            if self.cursor is None or self.cursor >= len(self.new_text):
                self.cursor = len(self.new_text)
            else: self.cursor = self.cursor + 1
        elif keyval_name in ("BackSpace", "Delete"):
            if self.cursor is None:
                self.cursor = 0
                self.new_text = ""
            else:
                if keyval_name == "BackSpace":
                    if self.cursor == 0: return True
                    else: self.cursor = self.cursor - 1
                if self.cursor == len(self.new_text): return True
                print(self.new_text)
                self.new_text = self.new_text[:self.cursor]+self.new_text[self.cursor+1:]
        elif len(e.string) == 1 and ord(e.string) >= ord(' '):
            #print(ord(e.string))
            if self.cursor is None:
                if e.string.islower() and self.new_text[:1].isupper():
                    self.new_text = e.string.upper()
                else: self.new_text = e.string
                self.cursor = 1
            else:
                self.new_text = self.new_text[:self.cursor] + e.string + self.new_text[self.cursor:]
                self.cursor = self.cursor + 1
        else:
            return False

        self.viewport.darea.queue_draw()
        return True

    def confirm_edit(self):
        self.env.change_name(self.obj_edit, self.new_text)
        self.reset()

    def on_reset(self):
        if self.no_cancel:
            self.no_cancel = False
            return
        if self.obj_edit is None: return
        if self.obj_edit < len(self.vis.gi_label_show):
            self.vis.gi_label_show[self.obj_edit] = True
        self.obj_edit = None
        self.viewport.edited_label = None
        self.viewport.app.keyboard_capture = None
        self.vis.visible_export()
        self.viewport.darea.queue_draw()

    def label_drag(self, coor, obj, objn, prev_hidden = True):
        scale = self.viewport.scale
        max_offset = 30
        if isinstance(objn, Point):
            pos = (coor - objn.a) * scale
            d = np.linalg.norm(pos) / max_offset
            if d > 1: pos /= d
        elif isinstance(objn, Circle):
            v = (coor - objn.c)
            if eps_zero(v): return
            direction = vector_direction(v)
            offset = (np.linalg.norm(v) - objn.r)*scale
            offset = np.clip(offset, -max_offset, max_offset)
            pos = direction, offset
        elif isinstance(objn, Line):
            endpoints = self.viewport.get_line_endpoints_ordered(objn)
            if endpoints is None: return
            v,n,c,e1,e2 = endpoints
            p1, p, p2 = (np.dot(e, v) for e in (e1, coor, e2))
            line_pos = np.clip((p-p1) / (p2-p1), 0.05, 0.95)
            offset = np.dot(n, coor) - c
            offset = np.clip(offset, -max_offset, max_offset)
            pos = line_pos, offset
        else: raise Exception("Unexpected type {}".format(type(objn)))

        self.vis.gi_label_position[obj] = pos
        if obj != self.obj_edit: self.on_reset()
        if self.obj_edit is None:
            self.vis.gi_label_show[obj] = True
            self.vis.visible_export()
            if prev_hidden:
                self.confirm = self.label_activate, obj, objn
        else:
            self.viewport.edited_label[0] = self.new_text
            self.viewport.edited_label[2] = pos
            self.viewport.darea.queue_draw()

            if self.cursor is None: self.confirm_next = self.update_basic
            else: self.confirm_next = self.update_edited
