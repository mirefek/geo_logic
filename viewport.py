import numpy as np
from itertools import islice
from geo_object import Point, Line, Circle, vector_perp_rot, vector_of_direction
from gtool import AmbiSelect
from gi.repository import Gtk, Gdk, GdkPixbuf

class Viewport:
    def __init__(self, env, scale = 1, shift = (0,0)):
        self.env = env
        self.scale = scale
        self.shift = np.array(shift)
        self.color_dict = dict()
        self.default_colors = [
            (0,    0, 0),   # default
            (0.6,  0, 0),   # ambiguous
            (0,    0, 0.7), # movable
        ]
        self.gtool = None
        self.ambi_select = AmbiSelect()
        self.shift_pressed = False

        self.click_hook = None

        self.mb_grasp = None
        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                              Gdk.EventMask.BUTTON_RELEASE_MASK |
                              Gdk.EventMask.SCROLL_MASK |
                              Gdk.EventMask.POINTER_MOTION_MASK )
        self.darea.connect("button-press-event", self.on_button_press)
        self.darea.connect("button-release-event", self.on_button_release)
        self.darea.connect("scroll-event", self.on_scroll)
        self.darea.connect("motion-notify-event", self.on_motion)
        self.darea.set_property('can-focus', True)

        self.load_cursors()

    def load_cursors(self):
        self.cursors = dict()
        import os
        names_png = [
            "basic", "point",
            "line", "perpline",
            "circle", "circumcircle",
            "reason", "hide",
        ]
        names_gtk = [
            "grab", "grabbing"
        ]
        cursor_dir = "images/cursors"
        display = Gdk.Display.get_default()
        for name in names_png:
            fname = os.path.join(cursor_dir, name+'.png')
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(fname)
            self.cursors[name] = Gdk.Cursor.new_from_pixbuf(
                display, pixbuf, 0, 0,
            )
        for name in names_gtk:
            self.cursors[name] = Gdk.Cursor.new_from_name(display, name)
        def realize(widget):
            self.set_cursor_by_tool()
        self.darea.connect("realize", realize)

    def set_cursor(self, name):
        #print("cursor:", name)
        if name is None: name = "basic"
        if name not in self.cursors:
            print("Warning: cannot set cursor '{}'".format(name))
            print(self.cursors.keys())
            return
        gdk_win = self.darea.get_window()
        if gdk_win is not None:
            gdk_win.set_cursor(self.cursors[name])

    def set_cursor_by_tool(self):
        cursor = None
        if self.gtool is not None:
            cursor = self.gtool.get_cursor()
        self.set_cursor(cursor)

    def set_tool(self, gtool):
        if self.gtool is not None: self.gtool.leave()
        if gtool is not None:
            gtool.enter(self)
            self.gtool = gtool
        self.set_cursor_by_tool()

    def update_shift_pressed(self, shift_pressed):
        if not isinstance(shift_pressed, bool):
            shift_pressed = bool(shift_pressed.state & Gdk.ModifierType.SHIFT_MASK)
        if self.shift_pressed and not shift_pressed:
            self.ambi_select.leave()
            self.set_cursor_by_tool()
        elif not self.shift_pressed and shift_pressed:
            self.gtool.cursor_away()
            self.ambi_select.enter(self)
            self.set_cursor(None)
        self.shift_pressed = shift_pressed
        if self.env.view_changed: self.darea.queue_draw()

    def on_button_press(self, w, e):
        hook_used = False
        if self.click_hook is not None:
            hook_used = self.click_hook()
        self.update_shift_pressed(e)

        if e.type != Gdk.EventType.BUTTON_PRESS: return
        coor = self.mouse_coor(e)
        shift = (e.state & Gdk.ModifierType.SHIFT_MASK)
        if e.button == 2:
            self.mb_grasp = coor
            return True

        if self.shift_pressed and e.button in (1,3):
            self.ambi_select.click(coor, e.button == 3)
            return True

        if e.button in (1,3):
            if e.button == 1:
                if not hook_used: self.gtool.button_press(coor)
            else: self.gtool.reset()
            if self.env.view_changed: self.darea.queue_draw()
            return True
    def on_button_release(self, w, e):
        self.update_shift_pressed(e)

        coor = self.mouse_coor(e)
        if not self.shift_pressed and e.button == 1:
            self.gtool.button_release(coor)
            if self.env.view_changed: self.darea.queue_draw()
            return True
    def on_motion(self,w,e):
        self.update_shift_pressed(e)

        if e.state & Gdk.ModifierType.BUTTON2_MASK:
            if self.mb_grasp is None: return
            self.shift_to_mouse(self.mb_grasp, e)
            self.darea.queue_draw()
        elif not self.shift_pressed:
            pressed = bool(e.state & Gdk.ModifierType.BUTTON1_MASK)
            coor = self.mouse_coor(e)
            self.gtool.motion(coor, pressed)
            if self.env.view_changed: self.darea.queue_draw()
    def on_scroll(self,w,e):
        self.update_shift_pressed(e)
        if e.direction == Gdk.ScrollDirection.DOWN:
            direction = 0.9
        elif e.direction == Gdk.ScrollDirection.UP:
            direction = 1/0.9
        else: return
        self.zoom(direction, e)
        self.darea.queue_draw()
        return True

    def point_dot(self, cr, p, pix_radius, fill = True):
        cr.arc(p.a[0], p.a[1], pix_radius / self.scale, 0, 2*np.pi)
        if fill: cr.fill()
    def draw_point(self, cr, p):
        self.point_dot(cr, p, 3)
    def point_shadow(self, cr, p, fill = True):
        self.point_dot(cr, p, 10, fill = fill)
    def draw_point_selection(self, cr, p):
        cr.save()
        self.set_select_color(cr)
        self.point_dot(cr, p, 8)
        cr.restore()
    def draw_point_proposal(self, cr, p):
        cr.save()
        cr.set_source_rgb(0, 0, 0)
        self.point_dot(cr, p, 4)
        cr.set_source_rgb(0.7, 0.9, 0.25)
        self.point_dot(cr, p, 3)
        cr.restore()

    def set_stroke(self, cr, pix_width, dashes = None):
        cr.set_line_width(pix_width / self.scale)
        if dashes is not None:
            cr.set_dash([d / self.scale for d in dashes])

    def draw_circle(self, cr, c, colorization = None):
        if colorization is None:
            cr.arc(c.c[0], c.c[1], c.r, 0, 2*np.pi)
            cr.stroke()
            return

        segments, selected, default_color = colorization
        if selected:
            cr.save()
            self.set_select_color(cr)
            self.set_stroke(cr, 3)
            if isinstance(selected, tuple): a, b = selected
            else: a, b = 0, 2
            self.raw_arc(cr, c.c, c.r, a, b)
            cr.stroke()
            cr.restore()

        for a,b, color in segments:
            #print("{} -> {} COLOR {}".format(a,b,color))
            self.raw_arc(cr, c.c, c.r, a, b)
            self.set_color(cr, color, default_color)
            cr.stroke()


    def get_line_endpoints(self, l):
        endpoints = [None, None]
        boundaries = list(zip(*self.corners))

        if np.prod(l.n) > 0:
            boundaries[1] = boundaries[1][1], boundaries[1][0]
        for coor in (0,1):
            if l.n[1-coor] == 0: continue
            for i, bound in enumerate(boundaries[coor]):
                p = np.zeros([2])
                p[coor] = bound
                p[1-coor] = (l.c - bound*l.n[coor])/l.n[1-coor]
                if (p[1-coor] - boundaries[1-coor][0]) * (p[1-coor] - boundaries[1-coor][1]) <= 0:
                    endpoints[i] = p

        if endpoints[0] is None or endpoints[1] is None: return None
        return endpoints

    def draw_parallel(self, cr, l, lev):
        endpoints = self.get_line_endpoints(l)
        if endpoints is None: return
        e1,e2 = endpoints
        if e1[0] > e2[0]: e1, e2 = e2, e1
        v, n = l.v, l.n
        if np.dot(e2-e1, v) < 0:
            v,n = -v,-n
        center = e2 - v * (70 / self.scale)
        shift = -v * (5 / self.scale)
        tick = (v*3 - n*5) / self.scale
        for _ in range(lev+2):
            cr.move_to(*(center + tick))
            cr.line_to(*(center - tick))
            cr.stroke()
            center += shift

    def draw_line(self, cr, l, colorization = None):

        endpoints = self.get_line_endpoints(l)
        if endpoints is None: return

        if colorization is None:
            cr.move_to(*endpoints[0])
            cr.line_to(*endpoints[1])
            cr.stroke()
            return

        segments, selected, default_color = colorization

        if selected:
            #print("selected")
            cr.save()
            self.set_select_color(cr)
            self.set_stroke(cr, 3)
            cr.move_to(*endpoints[0])
            cr.line_to(*endpoints[1])
            cr.stroke()
            cr.restore()

        #print("line colorized")
        e1, e2 = endpoints
        e1c = np.dot(e1, l.v)
        e2c = np.dot(e2, l.v)
        if e1c > e2c:
            e1,e2 = e2,e1
            e1c,e2c = e2c,e1c

        for a,b, color in segments:
            if a is None or a <= e1c: a = e1c
            elif a >= e2c: continue
            if b is None or b >= e2c: b = e2c
            elif b <= e1c: continue
            cr.move_to(*l.point_by_c(a))
            cr.line_to(*l.point_by_c(b))
            self.set_color(cr, color, default_color)
            cr.stroke()

    def draw_obj(self, cr, obj):
        if isinstance(obj, Point): self.draw_point(cr, obj)
        elif isinstance(obj, Line): self.draw_line(cr, obj)
        elif isinstance(obj, Circle): self.draw_circle(cr, obj)
        else: raise Exception("Unexpected type {}".format(type(obj)))

    def draw_helper(self, cr, obj):
        if isinstance(obj, tuple):
            self.draw_dist(cr, *obj)
        else: self.draw_obj(cr, obj)

    def draw_dist(self, cr, a,b,lev):
        if lev % 2 == 0: lev = -lev//2
        else: lev = (lev+1) // 2
        ab_v = (b-a) / np.linalg.norm(b-a)
        ab_n = vector_perp_rot(ab_v)
        a = a+(5*ab_v + 5*lev*ab_n)/self.scale
        b = b+(-5*ab_v + 5*lev*ab_n)/self.scale
        cr.move_to(*a)
        cr.line_to(*b)
        cr.stroke()

    def raw_arc(self, cr, center, radius, a, b):
        if radius <= 0: return
        if b < a: b += 2
        #print("{} -> {}".format(a, b))
        a *= np.pi
        b *= np.pi
        x,y = center
        cr.arc(x, y, radius, a, b)

    def draw_arc(self, cr, a,b,circ, lev):
        if lev % 2 == 0: lev = -lev//2
        else: lev = (lev+1) // 2
        r = circ.r + lev * 5/self.scale
        self.raw_arc(cr, circ.c, r, a, b)
        cr.stroke()

    def draw_angle(self, cr, coor, pos_a, pos_b, lev):
        r = (20 + 5*lev) / self.scale
        size = (pos_b - pos_a) % 2
        pos_a += 0.05*size
        pos_b -= 0.05*size
        self.raw_arc(cr, coor, r, pos_a, pos_b)
        cr.stroke()

    def draw_exact_angle(self, cr, coor, pos1, pos2):
        v1 = vector_of_direction(pos1) * (10 / self.scale)
        v2 = vector_of_direction(pos2) * (10 / self.scale)
        cr.move_to(*(coor+v1))
        cr.line_to(*(coor+v1+v2))
        cr.line_to(*(coor+v2))
        cr.stroke()

    def mouse_coor(self, e):
        return np.array([e.x, e.y])/self.scale - self.shift
    def shift_to_mouse(self, coor, mouse):
        self.shift = np.array([mouse.x, mouse.y])/self.scale - coor
    def zoom(self, scale_change, e):
        coor = self.mouse_coor(e)
        self.scale *= scale_change
        self.shift_to_mouse(coor, e)
        print("zoom {}".format(self.scale))

    def set_corners(self, width, height):
        self.corners = np.array([
            [0, 0],
            [width, height],
        ])/self.scale - self.shift

    def set_select_color(self, cr):
        cr.set_source_rgb(0.3, 1, 1)
    def set_color(self, cr, col_index, index2 = 0):
        if col_index < 0:
            alpha = 1./(-col_index)
            r,g,b = self.default_colors[index2]
            cr.set_source_rgba(r,g,b,alpha)
        else:
            if col_index in self.color_dict:
                cr.set_source_rgb(*self.color_dict[col_index])
                return
            hsv = Gtk.HSV()
            denom = 3
            start = 0
            jump = 1
            i = col_index
            while i >= denom // jump:
                i -= denom // jump
                denom *= 2
                start = 1
                jump = 2

            hue = (start+i*jump)/denom
            res = hsv.to_rgb(hue, 1, 1)
            lum = 1.2*res.r + 1.5*res.g + res.b
            color = (res.r/lum, res.g/lum, res.b/lum)

            self.color_dict[col_index] = color
            cr.set_source_rgb(*color)

    def draw_lies_on_l(self, cr, point, line):
        cr.save()
        self.point_shadow(cr, point, fill = False)
        cr.clip()
        self.draw_line(cr, *line)
        cr.restore()
    def draw_lies_on_c(self, cr, point, circle):
        cr.save()
        self.point_shadow(cr, point, fill = False)
        cr.clip()
        self.draw_circle(cr, *circle)
        cr.restore()
            
    def on_draw(self, wid, cr):
        self.env.view_changed = False
        self.set_corners(
            self.darea.get_allocated_width(),
            self.darea.get_allocated_height()
        )
        env = self.env

        # cr transform
        cr.scale(self.scale, self.scale)
        cr.translate(*self.shift)
        # erase background
        size = self.corners[1] - self.corners[0]
        cr.rectangle(*(list(self.corners[0])+list(size)))
        cr.set_source_rgb(1,1,1)
        cr.fill()

        # draw extra lines and circles
        self.set_stroke(cr, 1, [3])
        for line, points in env.extra_lines_numer:
            self.draw_line(cr, *line)
        for circle, points in env.extra_circles_numer:
            self.draw_circle(cr, *circle)

        # draw active lines and circles
        self.set_stroke(cr, 1, [])
        for line, points in env.active_lines_numer:
            self.draw_line(cr, *line)
        for circle, points in env.active_circles_numer:
            self.draw_circle(cr, *circle)

        # draw points shadows
        cr.set_source_rgb(1,1,1)
        for p,color,selected in env.visible_points_numer:
            self.point_shadow(cr, p)
            if selected: self.draw_point_selection(cr, p)

        # draw lies_on
        self.set_stroke(cr, 1, [3])
        for line, points in env.extra_lines_numer:
            for point in points:
                self.draw_lies_on_l(cr, point, line)
        for circle, points in env.extra_circles_numer:
            for point in points:
                self.draw_lies_on_c(cr, point, circle)
        self.set_stroke(cr, 1, [])
        for line, points in env.active_lines_numer:
            for point in points:
                self.draw_lies_on_l(cr, point, line)
        for circle, points in env.active_circles_numer:
            for point in points:
                self.draw_lies_on_c(cr, point, circle)

        # draw parallels
        self.set_color(cr, -1)
        for line, lev in env.visible_parallels:
            self.draw_parallel(cr, line, lev)

        # draw distances
        self.set_stroke(cr, 1, [3])
        for a,b,col,lev in env.visible_dists:
            self.set_color(cr, col)
            self.draw_dist(cr, a,b,lev)
        # draw arcs
        for a,b,circ,col,lev in env.visible_arcs:
            self.set_color(cr, col)
            self.draw_arc(cr, a,b,circ,lev)
        self.set_stroke(cr, 1, [])
        # draw angles
        for coor, pos_a, pos_b, col, lev in env.visible_angles:
            self.set_color(cr, col)
            self.draw_angle(cr, coor, pos_a, pos_b, lev)
        self.set_color(cr, -1)
        for coor, pos_a, pos_b in env.visible_exact_angles:
            self.draw_exact_angle(cr, coor, pos_a, pos_b)

        # draw helpers
        cr.save()
        self.set_stroke(cr, 2, [2])
        cr.set_source_rgb(0.5, 0.5, 0.5)
        for helper in env.hl_helpers:
            self.draw_helper(cr, helper)
        cr.restore()

        # draw points
        for p,color,selected in env.visible_points_numer:
            self.set_color(cr, -1, color)
            self.draw_point(cr, p)

        # draw proposals
        cr.set_source_rgb(0.5, 0.65, 0.17)
        for proposal in env.hl_proposals:
            if not isinstance(proposal, Point): self.draw_obj(cr, proposal)
        for proposal in env.hl_proposals:
            if isinstance(proposal, Point): self.draw_point_proposal(cr, proposal)
