import numpy as np
from itertools import islice
from geo_object import Point, Line, Circle, vector_perp_rot
from gi.repository import Gtk

class ViewPort:
    def __init__(self, scale = 1, shift = (0,0)):
        self.scale = scale
        self.shift = np.array(shift)

    def draw_point(self, cr, p):
        cr.arc(p.a[0], p.a[1], 3/self.scale, 0, 2*np.pi)
        cr.fill()
    def point_shadow(self, cr, p):
        cr.arc(p.a[0], p.a[1], 10/self.scale, 0, 2*np.pi)

    def draw_circle(self, cr, c, colorization = None):
        cr.set_line_width(1/self.scale)
        if colorization is not None:
            cr.save()
            print("circle colorized")
            for a,b, color in colorization:
                cr.arc(c.c[0], c.c[1], c.r, a, b)
                cr.set_source_rgb(*self.get_color(color))
                cr.stroke()
            cr.restore()
        else:
            cr.arc(c.c[0], c.c[1], c.r, 0, 2*np.pi)
            cr.stroke()

    def draw_line(self, cr, l, colorization = None):
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

        if endpoints[0] is None or endpoints[1] is None: return

        cr.set_line_width(1/self.scale)
        if colorization is not None:
            print("line colorized")
            e1, e2 = endpoints
            e1c = np.dot(e1, l.v)
            e2c = np.dot(e2, l.v)
            if e1c > e2c:
                e1,e2 = e2,e1
                e1c,e2c = e2c,e1c

            cr.save()
            for a,b, color in colorization:
                if a is None or a <= e1c: a = e1c
                elif a >= e2c: continue
                if b is None or b >= e2c: b = e2c
                elif b <= e1c: continue
                cr.move_to(l.point_by_c(a))
                cr.line_to(l.point_by_c(b))
                cr.set_source_rgb(*self.get_color(color))
                cr.stroke()
            cr.restore()
        else:
            cr.move_to(*endpoints[0])
            cr.line_to(*endpoints[1])
            cr.stroke()

    def draw_cline(self, cr, obj):
        if isinstance(obj, Line): self.draw_line(cr, obj)
        elif isinstance(obj, Circle): self.draw_circle(cr, obj)
        else: raise Exception("Unexpected type {}".format(type(obj)))

    def draw_dist(self, cr, a,b,lev):
        if lev % 2 == 0: lev = -lev//2
        else: lev = (lev+1) // 2
        ab_v = (b-a) / np.linalg.norm(b-a)
        ab_n = vector_perp_rot(ab_v)
        a = a+(5*ab_v + 5*lev*ab_n)/self.scale
        b = b+(-5*ab_v + 5*lev*ab_n)/self.scale
        cr.move_to(*a)
        cr.line_to(*b)
        cr.set_line_width(1/self.scale)
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
        self.corners = corners = np.array([
            [0, 0],
            [width, height],
        ])/self.scale - self.shift

    def get_color(self, col_index):
        hsv = Gtk.HSV()
        denom = 3
        start = 0
        jump = 1
        while col_index >= denom // jump:
            col_index -= denom // jump
            denom *= 2
            start = 1
            jump = 2

        hue = (start+col_index*jump)/denom
        res = hsv.to_rgb(hue, 1, 1)
        lum = 1.2*res.r + 1.5*res.g + res.b
        return (res.r/lum, res.g/lum, res.b/lum)

    def draw(self, cr, env):

        # cr transform
        cr.scale(self.scale, self.scale)
        cr.translate(*self.shift)
        # erase background
        size = self.corners[1] - self.corners[0]
        cr.rectangle(*(list(self.corners[0])+list(size)))
        cr.set_source_rgb(1,1,1)
        cr.fill()

        # draw circles and lines
        cr.set_source_rgb(0,0,0)
        for _,obj in env.visible_clines: self.draw_cline(cr, obj)

        # draw points shadows
        cr.set_source_rgb(1,1,1)
        for _,p in env.visible_points:
            self.point_shadow(cr, p)
            cr.fill()

        # draw lies_on
        cr.set_source_rgb(0,0,0)
        for p_li, ps_li in env.lies_on_data:
            p = env.li_to_num(p_li)
            ps = env.li_to_num(ps_li)
            cr.save()
            self.point_shadow(cr, p)
            cr.clip()
            self.draw_cline(cr, ps)
            cr.restore()

        # draw distances
        cr.save()
        cr.set_dash([3 / self.scale])
        for a,b,col,lev in env.dist_col_lev:
            cr.set_source_rgb(*self.get_color(col))
            self.draw_dist(cr, a,b,lev)
        cr.restore()

        # draw points
        cr.set_source_rgb(0,0,0)
        for _,p in env.visible_points:
            self.draw_point(cr, p)
