from gtool import GTool
from geo_object import *
import itertools
from primitive_constr import circumcircle
from primitive_pred import not_collinear

class GToolConstr(GTool):
    def lies_on(self, p, cl):
        if isinstance(p, tuple) and p[0] == self.smart_intersection:
            return cl in p[1:]
        else: return GTool.lies_on(self, p, cl)

    def intersect(self, cln1, cln2):
        if cln1 is cln2: return None
        if isinstance(cln1, Line) and isinstance(cln2, Line):
            x = intersection_ll(cln1, cln2)
            if x is None: return None
            else: return (x,)
        if isinstance(cln2, Line): cln1, cln2 = cln2, cln1
        if isinstance(cln1, Line): res = intersection_lc(cln1, cln2)
        else: res = intersection_cc(cln1, cln2)
        if len(res) <= 1: return None
        return tuple(res)

    def select_intersection(self, coor, point_on = None):
        if point_on is None:
            cl1,cln1 = self.select_cl(coor, permanent = False)
            if cl1 is None: return None,None
        else: cl1,cln1 = point_on

        candidates = []
        for cl2,cln2 in itertools.chain(
            self.env.selectable_lines,
            self.env.selectable_circles,
        ):
            if cl2 == cl1: continue
            dist_cl = cln2.dist_from(coor)
            if dist_cl >= self.find_radius: continue
            intersections = self.intersect(cln1, cln2)
            if intersections is None: continue
            for x in intersections:
                dist_x = np.linalg.norm(x-coor)
                if dist_x >= self.find_radius: continue
                candidates.append((dist_x, dist_cl, x, cl2, cln2))

        if not candidates:
            if point_on is None: self.hl_selected.pop()
            return None, None

        min_dist_x = min(dist_x for dist_x,_,_,_,_ in candidates)
        _,x,cl2,cln2 = min((
            (dist_cl,x,cl,cln)
            for dist_x,dist_cl,x,cl,cln in candidates
            if eps_identical(dist_x, min_dist_x)
        ))
        x = Point(x)
        self.hl_propose(x, permanent = True)
        self.hl_select(cl2)
        return (self.smart_intersection, x, cl1, cl2), x

    def select_pi(self, coor, point_on = None):
        if point_on is None: filter_f = None
        else:
            def filter_f(p,pn): return self.lies_on(p, point_on[0])
        p,pn = self.select_point(coor, filter_f = filter_f)
        if p is not None: return p,pn
        return self.select_intersection(coor, point_on = point_on)

    def smart_intersection(self, x, cl1, cl2, update = True):
        cln1 = self.env.gi_to_num(cl1)
        cln2 = self.env.gi_to_num(cl2)
        if isinstance(cln1, Line) and isinstance(cln2, Line):
            return self.run_tool("intersection", cl1, cl2, update = update)
        if isinstance(cln2, Line):
            cl1, cl2 = cl2, cl1
            cln1, cln2 = cln2, cln1

        x1,x2 = self.intersect(cln1, cln2)

        r = np.linalg.norm(x1 - x2) / 4
        if isinstance(cln1, Line):
            l = cl1
            lr = np.linalg.norm(x1 - x2) - 2*r
        else: l = None

        candidates = []
        l_candidates = []
        for p,pn in self.env.selectable_points:
            d1,d2 = (np.linalg.norm(x12-pn.a) for x12 in (x1,x2))
            d = min(d1, d2)

            if l is not None and self.lies_on(p, l):
                if not eps_smaller(abs(d1-d2), lr) : l_candidates.append((d,p))
            elif not eps_bigger(d, r): candidates.append((d,p))

        if l_candidates: candidates = l_candidates
        if candidates:
            _,p = min(candidates)
            return self.run_m_tool("intersection", x, cl1, cl2, p, update = update)
        return self.run_m_tool("intersection", x, cl1, cl2, update = update)

class ComboPoint(GToolConstr):

    def update_basic(self, coor):

        p, pn = self.select_point(coor)
        if p is not None:
            self.confirm_next = self.update_midpoint, p, pn
            return

        cl,cln = self.select_cl(coor)
        if cl is not None:
            self.drag = self.drag_intersection, cl, cln
            p,pn = self.select_intersection(coor, point_on = (cl,cln))
            if p is None:
                self.confirm = self.run_m_tool, "m_point_on", Point(coor), cl
            else: self.confirm = p
            return

        self.confirm = self.run_m_tool, "free_point", Point(coor)

    def update_midpoint(self, coor, p, pn):

        p2, pn2 = self.select_point(coor)
        if p2 is not None:
            if p2 == p or pn2.identical_to(pn): return
            self.hl_propose(Point((pn.a+pn2.a)/2), permanent = False)
            self.hl_add_helper((pn.a, pn2.a))
            self.confirm = self.run_tool, "midpoint", p, p2
            self.drag = self.drag_foot, p,pn, p2,pn2
            return

        cl, cln = self.select_cl(
            coor,
            filter_f = lambda l,ln: isinstance(ln, Circle) or not ln.contains(pn.a)
        )

        if cl is None:
            self.hl_propose(Point((pn.a+coor)/2))
            self.hl_add_helper((pn.a, coor))
            return

        if isinstance(cln, Circle):
            if eps_identical(cln.c, pn.a): return
            if self.lies_on(p, cl):
                op_point = Point(2*cln.c - pn.a)
                if np.linalg.norm(op_point.a - coor) < self.find_radius:
                    self.hl_propose(op_point)
                    self.confirm = self.run_tool, "opposite_point", p, cl
                else:
                    self.hl_selected.pop()
                    pos1 = vector_direction(pn.a - cln.c)
                    pos2 = vector_direction(coor - cln.c)
                    pos_arc = ((pos2-pos1) % 2) < 1
                    if pos_arc: self.hl_select((cl, pos1, pos1+1))
                    else: self.hl_select((cl, pos1+1, pos1), permanent = False)
                    self.confirm_next = self.select_arc_midpoint, p,pn, cl,cln, pos_arc
                return
            
        foot = cln.closest_on(pn.a)
        self.hl_propose(Point(foot))
        self.hl_add_helper((pn.a, foot))
        self.confirm = self.run_tool, "foot", p, cl

    def select_arc_midpoint(self, coor, p1,pn1, circ,circn, pos_arc):

        p2,pn2 = self.select_point(
            coor,
            filter_f = lambda p,pn: self.lies_on(p,circ)
        )

        if p2 is not None and p2 == p1:
            self.hl_select(circ)
            self.hl_propose(Point(2*circn.c - pn1.a))
            self.confirm = self.run_tool, "opposite_point", p1, circ
            return

        v1 = pn1.a - circn.c
        if p2 is None:
            if eps_identical(coor, circn.c): return
            v2 = coor - circn.c
            v2 *= circn.r / np.linalg.norm(v2)
        else: v2 = pn2.a - circn.c

        if eps_identical(v1, v2): return
        if not pos_arc: v1,v2 = v2,v1
        v = -vector_perp_rot(v1 - v2)
        v *= circn.r / np.linalg.norm(v)

        p = Point(circn.c + v)
        self.hl_propose(p)
        self.hl_select((circ, vector_direction(v1), vector_direction(v2)))

        if p2 is not None:
            if pos_arc: self.confirm = self.run_tool, "midpoint_arc", p1, p2, circ
            else: self.confirm = self.run_tool, "midpoint_arc", p2, p1, circ

    def drag_foot(self, coor, p,pn, p1,pn1):
        p2,pn2 = self.select_point(coor)
        if p2 is not None:
            if p2 == p1 or pn2.identical_to(pn1): return
            self.confirm = self.run_tool, "foot", p, p1, p2
            coor = pn2.a

        if eps_identical(pn1.a, coor): return
        l = line_passing_np_points(pn1.a, coor)
        foot = Point(l.closest_on(pn.a))
        self.hl_propose(foot)
        self.hl_add_helper(l, (pn.a, foot.a))

    def drag_intersection(self, coor, cl1,cln1):

        if isinstance(cln1, Circle):
            self.hl_add_helper(Point(cln1.c))
            if np.linalg.norm(coor - cln1.c) < self.find_radius:
                self.hl_propose(Point(cln1.c))
                self.confirm = self.run_tool, "center_of", cl1
                return

        cl2,cln2 = self.select_cl(coor)
        if cl2 is None or cl2 == cl1: return

        intersections = self.intersect(cln1, cln2)
        if intersections is None: return

        x = Point(min(intersections, key = lambda x: np.linalg.norm(x-coor)))
        self.hl_propose(x)
        self.confirm = self.smart_intersection, x, cl1, cl2

class ComboLine(GToolConstr):

    def update_basic(self, coor):
        p,pn = self.select_pi(coor)
        if p is not None:
            self.drag = self.drag_parallel, p, pn
            self.confirm_next = self.update_point2, p, pn
            return
        l,ln = self.select_line(coor)
        if l is not None:
            self.confirm_next = self.select_parallel, (l,), ln.n

    def update_point2(self, coor, p1, pn1):
        p2,pn2 = self.select_pi(coor)
        if p2 is not None:
            if p2 != p1 and not pn2.identical_to(pn1):
                l = line_passing_points(pn1, pn2)
                self.confirm = self.run_tool, "line", p1, p2
                self.drag = self.drag_angle_bisector, p1,pn1, p2,pn2
                self.hl_propose(l, permanent = False)
            return
        c,cn = self.select_circle(
            coor,
            filter_f = (lambda c,cn: self.lies_on(p1,c) or
                        eps_smaller(cn.r, np.linalg.norm(cn.c - pn1.a)))
        )
        if c is not None:
            if isinstance(cn, Circle):
                if self.lies_on(p1, c):
                    v = pn1.a - cn.c
                    self.confirm = self.run_tool, "tangent_at", p1, c
                    self.hl_propose(Line(v, np.dot(v, pn1.a)))
                else:
                    dia_rad = np.linalg.norm(pn1.a - cn.c)/2
                    if eps_zero(dia_rad): return
                    diacirc = Circle((pn1.a + cn.c)/2, dia_rad)
                    touchpoint_cand = intersection_cc(cn, diacirc)
                    if len(touchpoint_cand) < 2: return
                    i,touchpoint = min(
                        enumerate(touchpoint_cand),
                        key = lambda x: np.linalg.norm(x[1]-coor)
                    )
                    tangent_name = "tangent{}".format(i)
                    self.confirm = self.run_tool, tangent_name, p1, c
                    self.hl_propose(
                        Point(touchpoint),
                        line_passing_np_points(touchpoint, pn1.a),
                    )
            return

        l = line_passing_np_points(pn1.a, coor)
        self.confirm = self.run_m_tool, "m_line", l, p1
        self.hl_propose(l)

    def angle_bisector(self, A, B, C):
        v1 = A - B
        v2 = C - B
        v1 /= np.linalg.norm(v1)
        v2 /= np.linalg.norm(v2)
        if np.dot(v1, v2) > 0:
            n = vector_perp_rot(v1+v2)
        else:
            n = v1-v2
        return Line(n, np.dot(B, n))
    def drag_angle_bisector(self, coor, p,pn, p1,pn1):

        p2,pn2 = self.select_pi(coor)
        if p2 is not None:
            if p2 == p1:
                self.confirm = self.run_tool, "line", p, p1
                self.hl_propose(line_passing_points(pn,pn1))
                return
            coor = pn2.a

        self.hl_add_helper((pn.a,pn1.a))

        if eps_identical(coor, pn.a): return
        self.hl_add_helper((pn.a, coor))
        self.hl_propose(self.angle_bisector(pn1.a, pn.a, coor))
        if p2 is not None:
            self.confirm = self.run_tool, "angle_bisector_int", p1,p,p2

    def drag_parallel(self, coor, p1, pn1):
        p2,pn2 = self.select_pi(coor)
        if p2 is None:
            self.hl_add_helper(line_passing_np_points(pn1.a, coor))
        elif p2 != p1 and not pn2.identical_to(pn1):
            ln = line_passing_points(pn1, pn2)
            self.hl_add_helper(ln)
            self.confirm_next = self.select_parallel, (p1,p2), ln.n

    def select_parallel(self, coor, line_def, normal_vec):

        p,pn = self.select_pi(coor)
        if p is None:
            new_l = Line(normal_vec, np.dot(normal_vec, coor))
            self.hl_propose(new_l)
            direction = ("direction_of", *line_def)
            self.confirm = self.run_m_tool, "m_line_with_dir", new_l, direction
        else:
            new_l = Line(normal_vec, np.dot(normal_vec, pn.a))
            self.hl_propose(new_l)
            args = line_def+(p,)
            self.confirm = self.run_tool, "paraline", *args

class ComboPerpLine(GToolConstr):

    def update_basic(self, coor):
        p,pn = self.select_pi(coor)
        if p is not None:
            self.confirm_next = self.update_point2, p, pn
            self.drag = self.drag_perp, p, pn
            return
        l,ln = self.select_line(coor)
        if l is not None:
            self.confirm_next = self.select_perp, (l,), ln.v

    def perp_bisector(self, p1, p2):
        v = p1 - p2
        return Line(v, np.dot(v, p1+p2)/2)

    def update_point2(self, coor, p1, pn1):

        p2,pn2 = self.select_pi(coor)
        if p2 is None:
            l = self.perp_bisector(pn1.a, coor)
            self.hl_add_helper((pn1.a, coor))
            self.hl_propose(l)
        elif p2 != p1 and not pn2.identical_to(pn1):
            l = self.perp_bisector(pn1.a, pn2.a)
            self.confirm = self.run_tool, "perp_bisector", p1, p2
            self.drag = self.drag_angle_bisector, p1,pn1, p2,pn2
            self.hl_add_helper((pn1.a, pn2.a))
            self.hl_propose(l, permanent = False)

    def angle_bisector(self, A, B, C):
        v1 = A - B
        v2 = C - B
        v1 /= np.linalg.norm(v1)
        v2 /= np.linalg.norm(v2)
        if np.dot(v1, v2) > 0:
            n = v1+v2
        else:
            n = vector_perp_rot(v1-v2)
        return Line(n, np.dot(B, n))

    def drag_angle_bisector(self, coor, p,pn, p1,pn1):
        self.hl_add_helper((pn.a,pn1.a))

        p2,pn2 = self.select_pi(coor)
        if p2 is not None:
            if p2 == p1:
                self.confirm = self.run_tool, "perp_bisector", p, p1
                self.hl_propose(self.perp_bisector(pn.a, pn1.a))
                return
            coor = pn2.a

        if eps_identical(coor, pn.a): return
        self.hl_add_helper((pn.a, coor))
        self.hl_propose(self.angle_bisector(pn1.a, pn.a, coor))
        if p2 is not None:
            self.confirm = self.run_tool, "angle_bisector_ext", p1,p,p2

    def drag_perp(self, coor, p1, pn1):
        p2,pn2 = self.select_pi(coor)
        if p2 is None:
            l = line_passing_np_points(pn1.a, coor)
            self.hl_add_helper(l)
            self.hl_propose(Line(l.v, np.dot(l.v, coor)))
        elif p2 != p1 and not pn2.identical_to(pn1):
            l = line_passing_points(pn1, pn2)
            self.hl_add_helper(l)
            self.hl_propose(Line(l.v, np.dot(l.v, pn2.a)), permanent = False)
            self.confirm_next = self.select_perp, (p1,p2), l.v

    def select_perp(self, coor, line_def, normal_vec):
        p,pn = self.select_pi(coor)

        if p is None:
            new_l = Line(normal_vec, np.dot(normal_vec, coor))
            self.hl_propose(new_l)
            direction = "perp_direction", *line_def
            self.confirm = self.run_m_tool, "m_line_with_dir", new_l, direction
        else:
            nl = Line(normal_vec, np.dot(normal_vec, pn.a))
            self.hl_propose(nl)
            self.confirm = self.run_tool, "perpline", *(line_def+(p,))

class ComboCircle(GToolConstr):

    def update_basic(self, coor):
        p,pn = self.select_pi(coor)
        if p is not None:
            self.confirm_next = self.update_p, p, pn
            self.drag = self.drag_radius, p, pn
            return
        c,cn = self.select_circle(coor)
        if c is not None:
            r = ("radius_of", c)
            self.confirm_next = self.update_center, r,cn.r, None

    def update_p(self, coor, center, center_n):
        p, pn = self.select_pi(coor)
        if p is not None:
            if p != center and not pn.identical_to(center_n):
                new_c = Circle(center_n.a, np.linalg.norm(center_n.a-pn.a))
                self.hl_propose(new_c)
                self.confirm = self.run_tool, "circle", center, p
            return

        l, ln = self.select_line(
            coor, filter_f = lambda l,ln: not ln.contains(center_n.a)
        )
        if ln is not None:
            foot = ln.closest_on(center_n.a)
            circle = Circle(center_n.a, np.linalg.norm(foot - center_n.a))
            foot = Point(foot)
            self.hl_propose(circle, foot)
            self.confirm = self.make_tangent_to_line, center, l
            return

        new_c = Circle(center_n.a, np.linalg.norm(center_n.a-coor))
        self.hl_propose(new_c)
        self.confirm = self.run_m_tool, "m_circle_with_center", new_c, center

    def make_tangent_to_line(self, center, l):
        foot, = self.run_tool("foot", center, l, update = False)
        return self.run_tool("circle", center, foot)

    def drag_radius(self, coor, p1, pn1):
        p2, pn2 = self.select_pi(coor)
        if p2 is not None and not pn2.identical_to(pn1):
            rn = np.linalg.norm(pn2.a-pn1.a)
            new_c = Circle(pn2.a, rn)
            self.hl_propose(new_c, permanent = False)
            r = "dist", p1, p2
            self.confirm_next = self.update_center, r,rn, (pn1.a,pn2.a)
        elif not eps_identical(coor, pn1.a):
            c = Circle(coor, np.linalg.norm(coor-pn1.a))
            self.hl_propose(c)

    def update_center(self, coor, r,rn, radius_helper):
        if radius_helper is not None:
            self.hl_add_helper(radius_helper)
        center, center_n = self.select_pi(coor)
        if center is None:
            cn = Circle(coor, rn)
            self.hl_propose(cn)
            self.confirm = self.run_m_tool, "m_circle_with_radius", cn, r
        else:
            c = Circle(center_n.a, rn)
            self.hl_propose(c)
            args = r[1:]+(center,)
            self.confirm = self.run_tool, "compass", *args

class ComboCircumCircle(GToolConstr):

    def update_basic(self, coor):
        p1,pn1 = self.select_pi(coor)
        if p1 is not None:
            self.confirm_next = self.update_p, p1, pn1

    def update_p(self, coor, p1, pn1):
        p2,pn2 = self.select_pi(coor)
        if p2 is None:
            center = (pn1.a + coor)/2
            c = Circle(center, np.linalg.norm(center-coor))
            self.hl_propose(c)
            self.confirm = self.run_m_tool, "m_circle_passing1", c, p1
        elif p1 != p2 and not pn2.identical_to(pn1):
            center = (pn1.a + pn2.a)/2
            c = Circle(center, np.linalg.norm(center-pn2.a))
            self.hl_propose(c, permanent = False)
            self.confirm_next = self.update_pp, p1,pn1,p2,pn2

    def update_pp(self, coor, p1,pn1, p2,pn2):
        p3,pn3 = self.select_pi(coor)
        c = None
        if p3 is None:
            pn3 = Point(coor)
            if not_collinear(pn1,pn2,pn3):
                c = circumcircle(pn1,pn2,pn3)
                self.confirm = self.run_m_tool, "m_circle_passing2", c, p1,p2
        elif p3 == p2 or p3 == p1:
            center = (pn1.a + pn2.a)/2
            c = Circle(center, np.linalg.norm(center-pn2.a))
            self.confirm = self.run_tool, "diacircle", p1,p2
        elif not_collinear(pn1,pn2,pn3):
            c = circumcircle(pn1,pn2,pn3)
            self.confirm = self.run_tool, "circumcircle", p1,p2,p3

        if c is not None: self.hl_propose(c)
