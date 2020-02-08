import numpy as np
from itertools import islice
from geo_object import Point, Line, Circle, vector_perp_rot, vector_of_direction
from gi.repository import Gtk

class Viewport:
    def __init__(self, scale = 1, shift = (0,0)):
        self.scale = scale
        self.shift = np.array(shift)
        self.color_dict = dict()

    def draw_point(self, cr, p):
        cr.arc(p.a[0], p.a[1], 3/self.scale, 0, 2*np.pi)
        cr.fill()
    def point_shadow(self, cr, p):
        cr.arc(p.a[0], p.a[1], 10/self.scale, 0, 2*np.pi)
    def draw_point_selection(self, cr, p):
        cr.save()
        cr.set_source_rgb(0.3, 1, 1)
        cr.arc(p.a[0], p.a[1], 8/self.scale, 0, 2*np.pi)
        cr.fill()
        cr.restore()
    def draw_point_proposal(self, cr, p):
        cr.save()
        cr.set_source_rgb(0, 0, 0)
        cr.arc(p.a[0], p.a[1], 4, 0, 2*np.pi)
        cr.fill()
        cr.set_source_rgb(0.7, 0.9, 0.25)
        cr.arc(p.a[0], p.a[1], 3, 0, 2*np.pi)
        cr.fill()
        cr.restore()

    def draw_circle(self, cr, c, colorization = None, selected = False):
        if selected:
            cr.save()
            cr.set_source_rgb(0.3, 1, 1)
            cr.set_line_width(3)
            if isinstance(selected, tuple): a, b = selected
            else: a, b = 0, 2
            self.raw_arc(cr, c.c, c.r, a, b)
            cr.stroke()
            cr.restore()
        if colorization is not None:
            cr.save()
            #print("circle colorized")
            for a,b, color in colorization:
                #print("{} -> {} COLOR {}".format(a,b,color))
                self.raw_arc(cr, c.c, c.r, a, b)
                self.select_color(cr, color)
                cr.stroke()
            cr.restore()
        else:
            cr.arc(c.c[0], c.c[1], c.r, 0, 2*np.pi)
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

    def draw_line(self, cr, l, colorization = None, selected = None):

        endpoints = self.get_line_endpoints(l)
        if endpoints is None: return

        if selected:
            #print("selected")
            cr.save()
            cr.set_source_rgb(0.3, 1, 1)
            cr.set_line_width(3)
            cr.move_to(*endpoints[0])
            cr.line_to(*endpoints[1])
            cr.stroke()
            cr.restore()
        if colorization is not None:
            #print("line colorized")
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
                cr.move_to(*l.point_by_c(a))
                cr.line_to(*l.point_by_c(b))
                self.select_color(cr, color)
                cr.stroke()
            cr.restore()
        else:
            cr.move_to(*endpoints[0])
            cr.line_to(*endpoints[1])
            cr.stroke()

    def draw_obj(self, cr, obj):
        if isinstance(obj, Point): self.draw_point(cr, obj)
        elif isinstance(obj, Line): self.draw_line(cr, obj)
        elif isinstance(obj, Circle): self.draw_circle(cr, obj)
        else: raise Exception("Unexpected type {}".format(type(obj)))

    def draw_proposal(self, cr, obj):
        if isinstance(obj, Point): self.draw_point_proposal(cr, obj)
        else: self.draw_obj(cr, obj)

    def draw_helper(self, cr, obj):
        if isinstance(obj, tuple):
            a,b = obj
            cr.move_to(*a)
            cr.line_to(*b)
            cr.stroke()
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

    def select_color(self, cr, col_index):
        if col_index < 0:
            alpha = 1./(-col_index)
            cr.set_source_rgba(0,0,0,alpha)
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

    def draw_lies_on_l(self, cr, point, *line):
        cr.save()
        self.point_shadow(cr, point)
        cr.clip()
        self.draw_line(cr, *line)
        cr.restore()
    def draw_lies_on_c(self, cr, point, *circle):
        cr.save()
        self.point_shadow(cr, point)
        cr.clip()
        self.draw_circle(cr, *circle)
        cr.restore()
            
    def draw(self, cr, env):

        # cr transform
        cr.scale(self.scale, self.scale)
        cr.translate(*self.shift)
        # erase background
        size = self.corners[1] - self.corners[0]
        cr.rectangle(*(list(self.corners[0])+list(size)))
        cr.set_source_rgb(1,1,1)
        cr.fill()

        cr.set_line_width(1/self.scale)

        # draw extra lines and circles
        cr.set_dash([3 / self.scale])
        self.select_color(cr, -2)
        for line, colorization, points, selected in env.extra_lines_numer:
            self.draw_line(cr, line, colorization, selected)
        for circle, colorization, points, selected in env.extra_circles_numer:
            self.draw_circle(cr, circle, colorization, selected)
        cr.set_dash([])

        # draw active lines and circles
        self.select_color(cr, -1)
        for line, colorization, points, selected in env.active_lines_numer:
            self.draw_line(cr, line, colorization, selected)
        for circle, colorization, points, selected in env.active_circles_numer:
            self.draw_circle(cr, circle, colorization, selected)

        # draw points shadows
        cr.set_source_rgb(1,1,1)
        for p,selected in env.visible_points_numer:
            self.point_shadow(cr, p)
            cr.fill()
            if selected: self.draw_point_selection(cr, p)

        # draw lies_on
        cr.set_dash([3 / self.scale])
        self.select_color(cr, -2)
        for line, colorization, points, selected in env.extra_lines_numer:
            for point in points:
                self.draw_lies_on_l(cr, point, line, colorization, selected)
        for circle, colorization, points, selected in env.extra_circles_numer:
            for point in points:
                self.draw_lies_on_c(cr, point, circle, colorization, selected)
        cr.set_dash([])
        self.select_color(cr, -1)
        for line, colorization, points, selected in env.active_lines_numer:
            for point in points:
                self.draw_lies_on_l(cr, point, line, colorization, selected)
        for circle, colorization, points, selected in env.active_circles_numer:
            for point in points:
                self.draw_lies_on_c(cr, point, circle, colorization, selected)

        # draw parallels
        for line, lev in env.visible_parallels:
            self.draw_parallel(cr, line, lev)

        # draw distances
        cr.set_dash([3 / self.scale])
        for a,b,col,lev in env.visible_dists:
            self.select_color(cr, col)
            self.draw_dist(cr, a,b,lev)
        # draw arcs
        for a,b,circ,col,lev in env.visible_arcs:
            self.select_color(cr, col)
            self.draw_arc(cr, a,b,circ,lev)
        cr.set_dash([])
        # draw angles
        for coor, pos_a, pos_b, col, lev in env.visible_angles:
            self.select_color(cr, col)
            self.draw_angle(cr, coor, pos_a, pos_b, lev)
        self.select_color(cr, -1)
        for coor, pos_a, pos_b in env.visible_exact_angles:
            self.draw_exact_angle(cr, coor, pos_a, pos_b)

        # draw helpers
        cr.save()
        cr.set_line_width(2)
        cr.set_dash([1])
        cr.set_source_rgb(0.5, 0.5, 0.5)
        for helper in env.hl_helpers:
            self.draw_helper(cr, helper)
        cr.restore()

        # draw points
        self.select_color(cr, -1)
        for p,_ in env.visible_points_numer:
            self.draw_point(cr, p)

        # draw proposals
        cr.set_source_rgb(0.5, 0.65, 0.17)
        for proposal in env.hl_proposals:
            self.draw_proposal(cr, proposal)
