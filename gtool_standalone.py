#!/usr/bin/python3

import itertools
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
import cairo
from geo_object import *
from primitive_constr import circumcircle
from primitive_pred import not_collinear

def run_tuple(f, *args):
    if isinstance(f, tuple):
        args += f[1:]
        f = f[0]
    f(*args)

class GTool:
    def __init__(self, env, viewport):
        self.env = env
        self.viewport = viewport
        self.basic_init()
    def basic_init(self):
        self.view_changed = True
        self.dragged = False
        self.click_coor = None
        self.distance_to_drag = 5

        self.pre_update()
        self.update = self.update_basic
    def reset(self):
        self.basic_init()
        print("==== reset")
        #raise Exception()

    def pre_update(self):
        self.hl_proposals = []
        self.hl_selected = []
        self.hl_helpers = []
        self.drag = None
        self.confirm = None
        self.confirm_next = self.update_basic

    def hl_propose(self, *args):
        self.hl_proposals.extend(args)
    def hl_select(self, *args):
        self.hl_selected.extend(args)
    def hl_add_helper(self, *args):
        self.hl_helpers.extend(args)

    def run_update(self, coor):
        prev_proposals = self.hl_proposals
        prev_selected = self.hl_selected
        prev_helpers = self.hl_helpers
        self.pre_update()
        run_tuple(self.update, coor)
        self.view_changed = self.check_hl_change(
            prev_proposals, prev_selected, prev_helpers
        )
    def check_hl_change(self, prev_proposals, prev_selected, prev_helpers):
        if self.view_changed: return True
        if len(prev_proposals) != len(self.hl_proposals):
            return True
        if len(prev_selected) != len(self.hl_selected):
            return True
        if len(prev_helpers) != len(self.hl_helpers):
            return True
        for a,b in zip(prev_selected, self.hl_selected):
            if a is not b: return True
        for a,b in zip(prev_proposals, self.hl_proposals):
            if not a.identical_to(b): return True
        for a,b in zip(prev_helpers, self.hl_helpers):
            if type(a) != type(b): return True
            if isinstance(a, (Line, Point)):
                if not a.identical_to(b): return True
            else:
                a1,a2 = a
                b1,b2 = b
                if not eps_identical(a1,b1) or not eps_identical(a2,b2):
                    return True
        return False

    def run_confirm(self):
        if self.confirm is not None:
            run_tuple(self.confirm)
            self.view_changed = True
        self.update = self.confirm_next
    def button_press(self, coor):
        if self.click_coor is not None: self.reset()
        run_tuple(self.update, coor)
        if self.drag is None:
            self.run_confirm()
            self.run_update(coor)
        else:
            self.click_coor = coor
            self.dragged = False
    def button_release(self, coor):
        if self.click_coor is not None:
            click_coor = self.click_coor
            self.click_coor = None
            self.dragged = False
            self.run_confirm()
        self.run_update(coor)
    def motion(self, coor, button_pressed):
        if self.click_coor is not None:
            if not button_pressed:
                self.reset()
            elif not self.dragged:
                if np.linalg.norm(coor - self.click_coor) >= \
                   self.distance_to_drag / self.viewport.scale:
                    assert(self.drag is not None)
                    self.update = self.drag
                    self.dragged = True

        if self.click_coor is None or self.dragged:
            self.run_update(coor)

    # to be implemented
    def update_basic(self, coor):
        pass

class GToolTest(GTool):
    def click(self, coor):
        print("CLICK [{}, {}]".format(*coor))
    def drag_start(self, coor):
        print("Drag [{}, {}]...".format(*coor))
        return True
    def drag(self, coor):
        print("-> [{}, {}]...".format(*coor))
    def drag_finish(self, coor_start, coor_end):
        print("DRAG [{}, {}] -> [{}, {}]...".format(
            coor_start[0], coor_start[1], coor_end[0],  coor_end[1]
        ))

class ComboPointOri(GTool):
    def initialize(self):
        self.selected_point = None
        self.selected_arc = None
        self.drag_cl = None
        self.drag_p1 = None

    def click(self, coor):
        if self.selected_arc is not None:
            p1, circ, pos_arc = self.selected_arc
            self.selected_arc = None
            p2 = self.env.select_point(coor)
            if p2 is None:
                print("==== canceled 1")
            v = vector_perp_rot(p1.a - p2.a)
            v *= circ.r / np.linalg.norm(v)
            if pos_arc: v = -v
            print("Midpont arc")
            self.env.visible_points.append(
                Point(circ.c + v)
            )
        elif self.selected_point is not None:
            p = self.selected_point
            self.selected_point = None
            obj = self.env.select_pcl(coor)
            if obj is None:
                print("==== canceled 2")
            elif isinstance(obj, Point):
                print("Midpoint")
                self.env.visible_points.append(
                    Point((obj.a + p.a) / 2)
                )
            elif isinstance(obj, Line):
                if obj.contains(p.a):
                    print("==== canceled 3")
                else:
                    print("Line foot")
                    self.env.visible_points.append(
                        Point(obj.closest_on(p.a))
                    )
            elif isinstance(obj, Circle):
                if obj.contains(p.a):
                    radius = 30 / self.viewport.scale
                    op_point = 2*obj.c - p.a
                    if np.linalg.norm(op_point - coor) < radius:
                        print("Opposite point")
                        self.env.visible_points.append(
                            Point(op_point)
                        )
                    else:
                        pos = vector_direction(coor - obj.c) - vector_direction(p.a - obj.c)
                        pos_arc = (pos % 2) < 1
                        self.selected_arc = p, obj, pos_arc
                        print("selected arc", self.selected_arc)
                else:
                    print("Circle foot")
                    self.env.visible_points.append(
                        Point(obj.closest_on(p.a))
                    )
        else:
            obj = self.env.select_pcl(coor)
            if obj is None:
                print("Free point [{},{}]".format(*coor))
                self.env.visible_points.append(Point(coor))
                return
            elif isinstance(obj, Point):
                self.selected_point = obj
                print("... selected point", obj)
                return
            else:
                cl1 = obj

            # search for intersections
            candidates = []
            radius = 30 / self.viewport.scale
            for cl2 in itertools.chain(self.env.visible_lines, self.env.visible_circles):
                dist_cl = cl2.dist_from(coor)
                if dist_cl >= radius: continue
                intersections = self.intersect(cl1, cl2)
                if intersections is None: continue
                for x in intersections:
                    dist_x = np.linalg.norm(x-coor)
                    if dist_x >= radius: continue
                    candidates.append((dist_x, dist_cl, x, cl2))

            if not candidates:
                print("Dependent point [{},{}]".format(*coor))
                self.env.visible_points.append(
                    Point(cl1.closest_on(coor))
                )
            else:
                min_dist_x = min(dist_x for dist_x,_,_,_ in candidates)
                _,x,cl2 = min((
                    (dist_cl,x,cl)
                    for dist_x,dist_cl,x,cl in candidates
                    if eps_identical(dist_x, min_dist_x)
                ))
                print("Intersection 2")
                self.env.visible_points.append(Point(x))

    def drag_start(self, coor):
        self.selected_arc = None
        if self.selected_point is not None:
            self.drag_p1 = self.env.select_point(coor)
            if self.drag_p1 is not None: return True
            else: self.selected_point = None

        self.drag_cl = self.env.select_cl(coor)
        return self.drag_cl is not None

    def intersect(self, cl1, cl2):
        if cl1 is cl2: return None
        if isinstance(cl1, Line) and isinstance(cl2, Line):
            x = intersection_ll(cl1, cl2)
            if x is None: return None
            else: return (x,)
        if isinstance(cl2, Line): cl1, cl2 = cl2, cl1
        if isinstance(cl1, Line): res = intersection_lc(cl1, cl2)
        else: res = intersection_cc(cl1, cl2)
        if len(res) <= 1: return None
        return tuple(res)

    def drag_finish(self, coor_start, coor_end):
        if self.drag_p1 is not None:
            p = self.selected_point
            self.selected_point = None
            p1 = self.drag_p1
            self.drag_p1 = None
            p2 = self.env.select_point(coor_end)
            if p2 is None or p1.identical_to(p2):
                print("==== canceled 4")
                return
            l = line_passing_points(p1, p2)
            print("Line foot")
            self.env.visible_points.append(
                Point(l.closest_on(p.a))
            )
            return

        cl1 = self.drag_cl
        self.drag_cl = None

        radius = 30 / self.viewport.scale
        if isinstance(cl1, Circle) and np.linalg.norm(coor_end - cl1.c) < radius:
            print("Center")
            self.env.visible_points.append(Point(cl1.c))
            return

        cl2 = self.env.select_cl(coor_end, avoid = (cl1,))
        if cl2 is None:
            print("==== canceled 5")
            return

        intersections = self.intersect(cl1, cl2)
        if intersections is None:
            print("==== canceled 6")
            return
        if len(intersections) == 1:
            print("Intersection LL")
            self.env.visible_points.append(intersections[0])
        else:
            print("Intersection 2")
            x = min(intersections, key = lambda x: np.linalg.norm(x-coor_end))
            self.env.visible_points.append(Point(x))

class ComboPoint(GTool):

    def intersect(self, cl1, cl2):
        if cl1 is cl2: return None
        if isinstance(cl1, Line) and isinstance(cl2, Line):
            x = intersection_ll(cl1, cl2)
            if x is None: return None
            else: return (x,)
        if isinstance(cl2, Line): cl1, cl2 = cl2, cl1
        if isinstance(cl1, Line): res = intersection_lc(cl1, cl2)
        else: res = intersection_cc(cl1, cl2)
        if len(res) <= 1: return None
        return tuple(res)

    def update_basic(self, coor):

        radius = 30 / self.viewport.scale

        obj = self.env.select_pcl(coor)        
        if obj is None:
            self.confirm = self.free_point, coor
            return

        self.hl_select(obj)

        if isinstance(obj, Point):
            self.confirm_next = self.update_midpoint, obj
            return

        # search for intersections
        candidates = []
        cl1 = obj
        self.drag = self.drag_intersection, cl1
        for cl2 in itertools.chain(
                self.env.visible_lines, self.env.visible_circles
        ):
            if cl2 is cl1: continue
            dist_cl = cl2.dist_from(coor)
            if dist_cl >= radius: continue
            intersections = self.intersect(cl1, cl2)
            if intersections is None: continue
            for x in intersections:
                dist_x = np.linalg.norm(x-coor)
                if dist_x >= radius: continue
                candidates.append((dist_x, dist_cl, x, cl2))

        if not candidates:
            self.confirm = self.dep_point, coor, cl1
            return

        min_dist_x = min(dist_x for dist_x,_,_,_ in candidates)
        _,x,cl2 = min((
            (dist_cl,x,cl)
            for dist_x,dist_cl,x,cl in candidates
            if eps_identical(dist_x, min_dist_x)
        ))
        x = Point(x)
        self.hl_propose(x)
        self.hl_select(cl2)
        self.confirm = self.make_intersection, cl1, cl2, x

    def make_point(self, p):
        assert(isinstance(p, Point))
        self.env.visible_points.append(p)
    def free_point(self, coor):
        print("Free point")
        self.make_point(Point(coor))
    def dep_point(self, coor, cl):
        print("Dependent point")
        self.make_point(Point(cl.closest_on(coor)))
    def make_intersection(self, cl1, cl2, x):
        print("Intersection")
        self.make_point(x)

    def update_midpoint(self, coor, p):
        radius = 30 / self.viewport.scale

        self.hl_select(p)
        obj = self.env.select_pcl(coor)
        if obj is None:
            self.hl_propose(Point((p.a+coor)/2))
            self.hl_add_helper((p.a, coor))
            return

        self.hl_select(obj)
        if isinstance(obj, Point):
            if obj.identical_to(p): return
            self.hl_propose(Point((p.a+obj.a)/2))
            self.hl_add_helper((p.a, obj.a))
            self.confirm = self.make_midpoint, p, obj
            self.drag = self.drag_foot, p, obj
        elif isinstance(obj, Line):
            if obj.contains(p.a): return
            foot = obj.closest_on(p.a)
            self.hl_propose(Point(foot))
            self.hl_add_helper((p.a, foot))
            self.confirm = self.make_foot_l, p, obj
        else:
            assert(isinstance(obj, Circle))
            if eps_identical(obj.c, p.a): return
            if obj.contains(p.a):
                op_point = Point(2*obj.c - p.a)
                if np.linalg.norm(op_point.a - coor) < radius:
                    self.hl_select(obj)
                    self.hl_propose(op_point)
                    self.confirm = self.opposite_point, p, obj
                else:
                    self.hl_selected.pop()
                    pos1 = vector_direction(p.a - obj.c)
                    pos2 = vector_direction(coor - obj.c)
                    pos_arc = ((pos2-pos1) % 2) < 1
                    if pos_arc: self.hl_select((obj, pos1, pos1+1))
                    else: self.hl_select((obj, pos1+1, pos1))
                    self.confirm_next = self.select_arc_midpoint, p, obj, pos_arc
            else:
                foot = obj.closest_on(p.a)
                self.hl_propose(Point(foot))
                self.hl_add_helper((p.a, foot))
                self.confirm = self.make_foot_c, p, obj

    def make_midpoint(self, p1, p2):
        print("Midpoint P P")
        self.make_point(Point((p1.a+p2.a)/2))
    def make_foot_l(self, p, l):
        print("Foot P L")
        self.make_point(Point(l.closest_on(p.a)))
    def make_foot_c(self, p, c):
        print("Foot P C")
        self.make_point(Point(c.closest_on(p.a)))
    def make_foot_pp(self, p, p1, p2):
        print("Foot P P P")
        l = line_passing_points(p1, p2)
        self.make_point(Point(l.closest_on(p.a)))
    def opposite_point(self, p, circ):
        print("Opposite Point P C")
        self.make_point(Point(2*circ.c - p.a))
    def make_center(self, circ):
        print("Center C")
        self.make_point(Point(circ.c))

    def select_arc_midpoint(self, coor, p1, circ, pos_arc):
        self.hl_select(p1)

        p2 = self.env.select_point(coor, avoid = lambda p: not circ.contains(p.a))

        if p2 is not None and p2.identical_to(p1):
            self.hl_select(circ)
            self.hl_propose(Point(2*circ.c - p1.a))
            self.confirm = self.opposite_point, p1, circ
            return

        v1 = p1.a - circ.c
        if p2 is None:
            if eps_identical(coor, circ.c): return
            v2 = coor - circ.c
            v2 *= circ.r / np.linalg.norm(v2)
        else: v2 = p2.a - circ.c

        if eps_identical(v1, v2): return
        if not pos_arc: v1,v2 = v2,v1
        v = -vector_perp_rot(v1 - v2)
        v *= circ.r / np.linalg.norm(v)

        p = Point(circ.c + v)
        self.hl_propose(p)
        self.hl_select((circ, vector_direction(v1), vector_direction(v2)))

        if p2 is not None:
            self.hl_select(p2)
            if pos_arc: self.confirm = self.make_midpoint_arc, circ, p1, p2
            else: self.confirm = self.make_midpoint_arc, circ, p2, p1

    def make_midpoint_arc(self, circ, p1, p2):
        print("Midpoint Arc")
        v = vector_perp_rot(p1.a - p2.a)
        v *= -circ.r / np.linalg.norm(v)
        self.make_point(Point(circ.c + v))

    def drag_foot(self, coor, p, p1):
        self.hl_select(p, p1)
        p2 = self.env.select_point(coor)
        if p2 is not None:
            if p2.identical_to(p1): return
            self.hl_select(p2)
            self.confirm = self.make_foot_pp, p, p1, p2
            coor = p2.a

        if eps_identical(p1.a, coor): return
        l = line_passing_np_points(p1.a, coor)
        foot = Point(l.closest_on(p.a))
        self.hl_propose(foot)
        self.hl_add_helper(l, (p.a, foot.a))

    def drag_intersection(self, coor, cl1):
        self.hl_select(cl1)
        radius = 30 / self.viewport.scale

        if isinstance(cl1, Circle):
            self.hl_add_helper(Point(cl1.c))
            if np.linalg.norm(coor - cl1.c) < radius:
                self.hl_propose(Point(cl1.c))
                self.confirm = self.make_center, cl1
                return

        cl2 = self.env.select_cl(coor)
        if cl2 is None or cl2.identical_to(cl1): return
        self.hl_select(cl2)

        intersections = self.intersect(cl1, cl2)
        if intersections is None: return

        x = Point(min(intersections, key = lambda x: np.linalg.norm(x-coor)))
        self.hl_propose(x)
        self.confirm = self.make_intersection, cl1, cl2, x

class ComboLine(GTool):

    def update_basic(self, coor):
        obj = self.env.select_pl(coor)
        if obj is not None:
            self.hl_select(obj)
            if isinstance(obj, Point):
                self.drag = self.drag_parallel, obj
                self.confirm_next = self.update_point2, obj
            else:
                self.confirm_next = self.select_parallel, obj

    def update_point2(self, coor, p1):
        self.hl_select(p1)
        p2 = self.env.select_point(coor)
        if p2 is None:
            l = line_passing_np_points(p1.a, coor)
            self.confirm = self.make_free_line, p1, l
            self.hl_propose(l)
        elif not p2.identical_to(p1):
            l = line_passing_points(p1, p2)
            self.confirm = self.make_line_pp, p1, p2
            self.hl_select(p2)
            self.hl_propose(l)

    def drag_parallel(self, coor, p1):
        self.hl_select(p1)
        p2 = self.env.select_point(coor)
        if p2 is None or p2.identical_to(p1):
            if not eps_identical(p1.a, coor):
                self.hl_add_helper(line_passing_np_points(p1.a, coor))
        else:
            l = line_passing_np_points(p1.a, p2.a)
            self.hl_select(p2)
            self.hl_add_helper(l)
            self.confirm_next = self.select_parallel, l, p1,p2

    def make_line(self, l):
        assert(isinstance(l, Line))
        self.env.visible_lines.append(l)
    def make_line_pp(self, p1, p2):
        print("Line P P")
        self.make_line(line_passing_points(p1, p2))
    def make_free_line(self, p1, l):
        print("Line P")
        self.make_line(l)

    def select_parallel(self, coor, l, p1 = None, p2 = None):
        p = self.env.select_point(coor)

        if p1 is None:
            self.hl_select(l)
            line_def = l
        else:
            self.hl_select(p1,p2)
            line_def = (p1, p2)

        if p is None:
            nl = Line(l.n, np.dot(l.n, coor))
            self.hl_propose(nl)
            self.confirm = self.make_free_parallel, line_def, nl
        else:
            self.hl_select(p)
            nl = Line(l.n, np.dot(l.n, p.a))
            self.hl_propose(nl)
            self.confirm = self.make_parallel, line_def, p, nl

    def make_parallel(self, line_def, p, nl):
        if isinstance(line_def, tuple): print("Parallel P P P")
        else: print("Parallel L P")
        self.make_line(nl)
    def make_free_parallel(self, line_def, nl):
        if isinstance(line_def, tuple): print("Free Parallel P P")
        else: print("Free Parallel L")
        self.make_line(nl)

class ComboPerpLine(GTool):

    def update_basic(self, coor):
        obj = self.env.select_pl(coor)
        if obj is not None:
            self.hl_select(obj)
            if isinstance(obj, Point):
                self.confirm_next = self.update_point2, obj
                self.drag = self.drag_perp, obj
            else:
                self.confirm_next = self.select_perp, obj

    def perp_bisector(self, p1, p2):
        v = p1 - p2
        return Line(v, np.dot(v, p1+p2)/2)

    def update_point2(self, coor, p1):
        self.hl_select(p1)
        p2 = self.env.select_point(coor)
        if p2 is None:
            l = self.perp_bisector(p1.a, coor)
            self.hl_add_helper((p1.a, coor))
            self.hl_propose(l)
        elif not p2.identical_to(p1):
            self.hl_select(p2)
            l = self.perp_bisector(p1.a, p2.a)
            self.confirm = self.make_bisector, p1, p2
            self.hl_add_helper((p1.a, p2.a))
            self.hl_propose(l)

    def drag_perp(self, coor, p1):
        self.hl_select(p1)
        p2 = self.env.select_point(coor)
        if p2 is None or p2.identical_to(p1):
            if not eps_identical(p1.a, coor):
                l = line_passing_np_points(p1.a, coor)
                self.hl_add_helper(l)
                self.hl_propose(Line(l.v, np.dot(l.v, coor)))
        else:
            self.hl_select(p2)
            l = line_passing_np_points(p1.a, p2.a)
            self.hl_add_helper(l)
            self.hl_propose(Line(l.v, np.dot(l.v, p2.a)))
            self.confirm_next = self.select_perp, l, p1,p2

    def make_line(self, l):
        assert(isinstance(l, Line))
        self.env.visible_lines.append(l)
    def make_bisector(self, p1, p2):
        print("Line P P")
        self.make_line(self.perp_bisector(p1.a, p2.a))

    def select_perp(self, coor, l, p1 = None, p2 = None):
        p = self.env.select_point(coor)

        if p1 is None:
            self.hl_select(l)
            line_def = l
        else:
            self.hl_select(p1,p2)
            line_def = (p1, p2)

        if p is None:
            nl = Line(l.v, np.dot(l.v, coor))
            self.hl_propose(nl)
            self.confirm = self.make_free_perp, line_def, nl
        else:
            self.hl_select(p)
            nl = Line(l.v, np.dot(l.v, p.a))
            self.hl_propose(nl)
            self.confirm = self.make_perp, line_def, p, nl

    def make_perp(self, line_def, p, nl):
        if isinstance(line_def, tuple): print("Perpline P P P")
        else: print("Perpline L P")
        self.make_line(nl)
    def make_free_perp(self, line_def, nl):
        if isinstance(line_def, tuple): print("Free Perpline P P")
        else: print("Free Perpline l L")
        self.make_line(nl)

class ComboCircle(GTool):

    def update_basic(self, coor):
        p = self.env.select_point(coor)
        if p is not None:
            self.hl_select(p)
            self.confirm_next = self.update_p, p
            self.drag = self.drag_radius, p

    def update_p(self, coor, center):
        p = self.env.select_point(coor)
        self.hl_select(center)
        if p is None:
            c = Circle(center.a, np.linalg.norm(center.a-coor))
            self.hl_propose(c)
            self.confirm = self.free_circle, center, c
        elif not p.identical_to(center):
            self.hl_select(p)
            c = Circle(center.a, np.linalg.norm(center.a-p.a))
            self.hl_propose(c)
            self.confirm = self.make_circle_pp, center, p, c

    def make_circle(self, c):
        assert(isinstance(c, Circle))
        self.env.visible_circles.append(c)
    def make_circle_pp(self, center,p, c):
        print("Free Circle P")
        self.make_circle(c)
    def free_circle(self, center, c):
        print("Circle P P")
        self.make_circle(c)

    def drag_radius(self, coor, p1):
        self.hl_select(p1)
        p2 = self.env.select_point(coor)
        if p2 is not None and not p2.identical_to(p1):
            self.hl_select(p2)
            r = np.linalg.norm(p2.a-p1.a)
            c = Circle(p2.a, r)
            self.hl_propose(c)
            self.confirm_next = self.update_center, r, p1,p2
        elif not eps_identical(coor, p1.a):
            c = Circle(coor, np.linalg.norm(coor-p1.a))
            self.hl_propose(c)

    def update_center(self, coor, r, p1,p2):
        self.hl_select(p1,p2)
        self.hl_add_helper((p1.a,p2.a))
        center = self.env.select_point(coor)
        if center is None:
            c = Circle(coor, r)
            self.hl_propose(c)
            self.confirm = self.free_compass, p1,p2, c
        else:
            self.hl_select(center)
            c = Circle(center.a, r)
            self.hl_propose(c)
            self.confirm = self.compass, p1,p2,center, c

    def free_compass(self, p1, p2, c):
        print("Free Compass P P")
        self.make_circle(c)
    def compass(self, p1, p2, center, c):
        print("Compass P P P")
        self.make_circle(c)

class ComboCircumCircle(GTool):

    def update_basic(self, coor):
        p1 = self.env.select_point(coor)
        if p1 is not None:
            self.hl_select(p1)
            self.confirm_next = self.update_p, p1

    def update_p(self, coor, p1):
        self.hl_select(p1)
        p2 = self.env.select_point(coor)
        if p2 is None:
            center = (p1.a + coor)/2
            c = Circle(center, np.linalg.norm(center-coor))
            self.hl_propose(c)
            self.confirm = self.free_circle_p, p1, c
        elif not p2.identical_to(p1):
            self.hl_select(p2)
            center = (p1.a + p2.a)/2
            c = Circle(center, np.linalg.norm(center-p2.a))
            self.hl_propose(c)
            self.confirm_next = self.update_pp, p1,p2

    def update_pp(self, coor, p1,p2):
        self.hl_select(p1,p2)
        p3 = self.env.select_point(coor)
        c = None
        if p3 is None:
            p3 = Point(coor)
            if not_collinear(p1,p2,Point(coor)):
                c = circumcircle(p1,p2,p3)
                self.confirm = self.free_circle_pp, p1,p2, c
        elif p3.identical_to(p2) or p3.identical_to(p1):
            center = (p1.a + p2.a)/2
            c = Circle(center, np.linalg.norm(center-p2.a))
            self.confirm = self.dia_circle, p1,p2,c
        elif not_collinear(p1,p2,p3):
            self.hl_select(p3)
            c = circumcircle(p1,p2,p3)
            self.confirm = self.circumcircle, p1,p2,p3,c

        if c is not None: self.hl_propose(c)

    def make_circle(self, c):
        assert(isinstance(c, Circle))
        self.env.visible_circles.append(c)
    def free_circle_p(self, p, c):
        print("Free Circle P")
        self.make_circle(c)
    def free_circle_pp(self, p1, p2, c):
        print("Free Circle P P")
        self.make_circle(c)
    def dia_circle(self, p1, p2, c):
        print("DiaCircle P P")
        self.make_circle(c)
    def circumcircle(self, p1, p2, p3, c):
        print("CircumCircle P")
        self.make_circle(c)

class Environment:
    def __init__(self):
        self.visible_points = []
        self.visible_circles = []
        self.visible_lines = []
    def select_obj_from(self, coor, lists, avoid = None, radius = 30):
        candidates = []
        for l in lists:
            if not l: continue
            candidate = min((p.dist_from(coor), p) for p in l)
            if candidate[0] >= radius: continue
            if avoid is not None and avoid(candidate[1]): continue
            if l is self.visible_points: return candidate[1]
            candidates.append(candidate)
        if not candidates: return None
        return min(candidates)[1]

    def select_point(self, coor, **kwargs):
        return self.select_obj_from(coor, (self.visible_points,), **kwargs)
    def select_line(self, coor, **kwargs):
        return self.select_obj_from(coor, (self.visible_lines,), **kwargs)
    def select_circle(self, coor, **kwargs):
        return self.select_obj_from(coor, (self.visible_circles,), **kwargs)
    def select_cl(self, coor, **kwargs):
        return self.select_obj_from(coor, (self.visible_lines,self.visible_circles), **kwargs)
    def select_pc(self, coor, **kwargs):
        return self.select_obj_from(coor, (self.visible_points,self.visible_circles), **kwargs)
    def select_pl(self, coor, **kwargs):
        return self.select_obj_from(coor, (self.visible_points,self.visible_lines), **kwargs)
    def select_pcl(self, coor, **kwargs):
        return self.select_obj_from(coor, (
            self.visible_points, self.visible_lines, self.visible_circles
        ), **kwargs)

class Viewport:
    def __init__(self):
        self.scale = 1

class Drawing(Gtk.Window):

    def __init__(self, win_size):
        super(Drawing, self).__init__()
        self.env = Environment()
        self.viewport = Viewport()

        self.key_to_gtool = {
            'x' : ComboPoint,
            'l' : ComboLine,
            't' : ComboPerpLine,
            'T' : ComboPerpLine,
            'c' : ComboCircle,
            'o' : ComboCircumCircle,
        }
        self.cur_tool = ComboPoint(self.env, self.viewport)

        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                              Gdk.EventMask.BUTTON_RELEASE_MASK |
                              Gdk.EventMask.KEY_PRESS_MASK |
                              Gdk.EventMask.POINTER_MOTION_MASK)
        self.add(self.darea)
        self.update_hl()

        self.darea.connect("button-press-event", self.on_button_press)
        self.darea.connect("button-release-event", self.on_button_release)
        self.darea.connect("motion-notify-event", self.on_motion)
        self.connect("key-press-event", self.on_key_press)

        self.set_title("Drawing")
        self.resize(*win_size)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", Gtk.main_quit)
        self.show_all()

    def get_line_endpoints(self, l, corners):
        endpoints = [None, None]
        boundaries = list(zip(*corners))

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

    def on_draw(self, wid, cr):

        print("draw")

        corners = np.array([
            [0, 0],
            [self.darea.get_allocated_width(), self.darea.get_allocated_height()],
        ])
        size = corners[1] - corners[0]
        cr.rectangle(*(list(corners[0])+list(size)))
        cr.set_source_rgb(1, 1, 1)
        cr.fill()

        cr.set_source_rgb(0.3, 1, 1)
        cr.set_line_width(3)
        for obj in self.hl_selected:
            if isinstance(obj, tuple):
                obj, pos1, pos2 = obj
            else: pos1,pos2 = None,None
            if isinstance(obj, Point):
                cr.arc(obj.a[0], obj.a[1], 8, 0, 2*np.pi)
                cr.fill()
            elif isinstance(obj, Line):
                endpoints = self.get_line_endpoints(obj, corners)
                cr.move_to(*endpoints[0])
                cr.line_to(*endpoints[1])
                cr.stroke()
            else:
                assert(isinstance(obj, Circle))
                if pos1 is None: cr.arc(obj.c[0], obj.c[1], obj.r, 0, 2*np.pi)
                else:
                    if pos2 <= pos1: pos2 += 2
                    cr.arc(obj.c[0], obj.c[1], obj.r, pos1*np.pi, pos2*np.pi)
                cr.stroke()

        cr.set_source_rgb(0, 0, 0)
        cr.set_line_width(1)
        for circle in self.env.visible_circles:
            cr.arc(circle.c[0], circle.c[1], circle.r, 0, 2*np.pi)
            cr.stroke()
        for line in self.env.visible_lines:
            endpoints = self.get_line_endpoints(line, corners)
            cr.move_to(*endpoints[0])
            cr.line_to(*endpoints[1])
            cr.stroke()

        cr.save()
        cr.set_line_width(1.5)
        cr.set_dash([1])
        cr.set_source_rgb(0.5, 0.5, 0.5)
        for obj in self.hl_helpers:
            if isinstance(obj, tuple):
                a,b = obj
                cr.move_to(*a)
                cr.line_to(*b)
                cr.stroke()
            elif isinstance(obj, Line):
                endpoints = self.get_line_endpoints(obj, corners)
                cr.move_to(*endpoints[0])
                cr.line_to(*endpoints[1])
                cr.stroke()
            elif isinstance(obj, Point):
                cr.arc(obj.a[0], obj.a[1], 3, 0, 2*np.pi)
                cr.fill()
                
        cr.set_dash([])
        cr.restore()

        cr.set_source_rgb(0, 0, 0)
        for point in self.env.visible_points:
            cr.arc(point.a[0], point.a[1], 3, 0, 2*np.pi)
            cr.fill()

        cr.set_source_rgb(0.5, 0.65, 0.17)
        for obj in self.hl_proposals:
            if isinstance(obj, Point):
                cr.save()
                cr.set_source_rgb(0, 0, 0)
                cr.arc(obj.a[0], obj.a[1], 4, 0, 2*np.pi)
                cr.fill()
                cr.set_source_rgb(0.7, 0.9, 0.25)
                cr.arc(obj.a[0], obj.a[1], 3, 0, 2*np.pi)
                cr.fill()
                cr.restore()
            elif isinstance(obj, Line):
                endpoints = self.get_line_endpoints(obj, corners)
                cr.move_to(*endpoints[0])
                cr.line_to(*endpoints[1])
                cr.stroke()
            else:
                cr.arc(obj.c[0], obj.c[1], obj.r, 0, 2*np.pi)
                cr.stroke()

    def on_key_press(self,w,e):

        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        if keyval_name in self.key_to_gtool:
            gtool = self.key_to_gtool[keyval_name]
            print("change tool -> {}".format(gtool.__name__))
            self.cur_tool = gtool(self.env, self.viewport)
        elif keyval_name == "Escape":
            Gtk.main_quit()
        else: print(keyval_name)

    def get_coor(self, e):
        return np.array([e.x, e.y])

    def on_button_press(self, w, e):
        if e.type != Gdk.EventType.BUTTON_PRESS: return

        coor = self.get_coor(e)
        if e.button == 1:
            self.cur_tool.button_press(coor)
        elif e.button == 3:
            self.cur_tool.reset()
        self.update_hl()

    def on_button_release(self, w, e):
        coor = self.get_coor(e)
        self.cur_tool.button_release(coor)
        self.update_hl()

    def on_motion(self, w, e):
        coor = self.get_coor(e)
        self.cur_tool.motion(coor, bool(e.state & Gdk.ModifierType.BUTTON1_MASK))
        self.update_hl()

    def update_hl(self):
        if self.cur_tool.view_changed:
            self.hl_proposals = self.cur_tool.hl_proposals
            self.hl_selected = self.cur_tool.hl_selected
            self.hl_helpers = self.cur_tool.hl_helpers
            self.cur_tool.view_changed = False
            self.darea.queue_draw()

win = Drawing((800, 600))
Gtk.main()
