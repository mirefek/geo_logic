from gtool import GTool
from geo_object import *
import itertools
from primitive_constr import circumcircle
from primitive_pred import not_collinear

class ComboPoint(GTool):

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

    def update_basic(self, coor):

        obj, objn = self.coor_to_pcl(coor)
        if obj is None:
            self.confirm = self.run_m_tool, "free_point", Point(coor)
            return

        self.hl_select(obj)

        if isinstance(objn, Point):
            self.confirm_next = self.update_midpoint, obj, objn
            return

        # search for intersections
        candidates = []
        cl1,cln1 = obj, objn
        self.drag = self.drag_intersection, cl1, cln1
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
            self.confirm = self.run_m_tool, "m_point_on", Point(coor), cl1
            return

        min_dist_x = min(dist_x for dist_x,_,_,_,_ in candidates)
        _,x,cl2,cln2 = min((
            (dist_cl,x,cl,cln)
            for dist_x,dist_cl,x,cl,cln in candidates
            if eps_identical(dist_x, min_dist_x)
        ))
        x = Point(x)
        self.hl_propose(x)
        self.hl_select(cl2)
        self.confirm = self.smart_intersection, x, cl1, cl2

    def update_midpoint(self, coor, p, pn):

        self.hl_select(p)
        obj, objn = self.coor_to_pcl(
            coor,
            avoid = lambda l,ln: isinstance(ln, Line) and ln.contains(pn.a)
        )

        if obj is None:
            self.hl_propose(Point((pn.a+coor)/2))
            self.hl_add_helper((pn.a, coor))
            return

        self.hl_select(obj)
        if isinstance(objn, Point):
            if obj == p or objn.identical_to(pn): return
            self.hl_propose(Point((pn.a+objn.a)/2))
            self.hl_add_helper((pn.a, objn.a))
            self.confirm = self.run_tool, "midpoint", p, obj
            self.drag = self.drag_foot, p,pn, obj, objn
        elif isinstance(objn, Line):
            foot = objn.closest_on(pn.a)
            self.hl_propose(Point(foot))
            self.hl_add_helper((pn.a, foot))
            self.confirm = self.run_tool, "foot", p, obj
        else:
            assert(isinstance(objn, Circle))
            if eps_identical(objn.c, pn.a): return
            if self.lies_on(p, obj):
                op_point = Point(2*objn.c - pn.a)
                if np.linalg.norm(op_point.a - coor) < self.find_radius:
                    self.hl_select(obj)
                    self.hl_propose(op_point)
                    self.confirm = self.run_tool, "opposite_point", p, obj
                else:
                    self.hl_selected.pop()
                    pos1 = vector_direction(pn.a - objn.c)
                    pos2 = vector_direction(coor - objn.c)
                    pos_arc = ((pos2-pos1) % 2) < 1
                    if pos_arc: self.hl_select((obj, pos1, pos1+1))
                    else: self.hl_select((obj, pos1+1, pos1))
                    self.confirm_next = self.select_arc_midpoint, p,pn, obj,objn, pos_arc
            elif not objn.contains(pn.a):
                foot = objn.closest_on(pn.a)
                self.hl_propose(Point(foot))
                self.hl_add_helper((pn.a, foot))
                self.confirm = self.run_tool, "foot", p, obj

    def select_arc_midpoint(self, coor, p1,pn1, circ,circn, pos_arc):
        self.hl_select(p1)

        p2,pn2 = self.coor_to_point(
            coor,
            avoid = lambda p,pn: not self.lies_on(p,circ)
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
            self.hl_select(p2)
            if pos_arc: self.confirm = self.run_tool, "midpoint_arc", p1, p2, circ
            else: self.confirm = self.run_tool, "midpoint_arc", p2, p1, circ

    def drag_foot(self, coor, p,pn, p1,pn1):
        self.hl_select(p, p1)
        p2,pn2 = self.coor_to_point(coor)
        if p2 is not None:
            if p2 == p1 or pn2.identical_to(pn1): return
            self.hl_select(p2)
            self.confirm = self.run_tool, "foot", p, p1, p2
            coor = pn2.a

        if eps_identical(pn1.a, coor): return
        l = line_passing_np_points(pn1.a, coor)
        foot = Point(l.closest_on(pn.a))
        self.hl_propose(foot)
        self.hl_add_helper(l, (pn.a, foot.a))

    def drag_intersection(self, coor, cl1,cln1):
        self.hl_select(cl1)

        if isinstance(cln1, Circle):
            self.hl_add_helper(Point(cln1.c))
            if np.linalg.norm(coor - cln1.c) < self.find_radius:
                self.hl_propose(Point(cln1.c))
                self.confirm = self.run_tool, "center_of", cl1
                return

        cl2,cln2 = self.coor_to_cl(coor)
        if cl2 is None or cl2 == cl1: return
        self.hl_select(cl2)

        intersections = self.intersect(cln1, cln2)
        if intersections is None: return

        x = Point(min(intersections, key = lambda x: np.linalg.norm(x-coor)))
        self.hl_propose(x)
        self.confirm = self.smart_intersection, x, cl1, cl2

    def smart_intersection(self, x, cl1, cl2):
        cln1 = self.env.gi_to_num(cl1)
        cln2 = self.env.gi_to_num(cl2)
        if isinstance(cln1, Line) and isinstance(cln2, Line):
            self.run_tool("intersection", cl1, cl2)
            return
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
            return self.run_m_tool("intersection", x, cl1, cl2, p)
        return self.run_m_tool("intersection", x, cl1, cl2)

class ComboLine(GTool):

    def update_basic(self, coor):
        obj,objn = self.coor_to_pl(coor)
        if obj is not None:
            self.hl_select(obj)
            if isinstance(objn, Point):
                self.drag = self.drag_parallel, obj, objn
                self.confirm_next = self.update_point2, obj, objn
            else:
                self.confirm_next = self.select_parallel, (obj,), objn.n

    def update_point2(self, coor, p1, pn1):
        self.hl_select(p1)
        p2,pn2 = self.coor_to_pc(coor)
        if p2 is None:
            l = line_passing_np_points(pn1.a, coor)
            self.confirm = self.run_m_tool, "m_line", l, p1
            self.hl_propose(l)
        else:
            self.hl_select(p2)
            if isinstance(pn2, Circle):
                if self.lies_on(p1, p2):
                    v = pn1.a - pn2.c
                    self.confirm = self.run_tool, "tangent_at", p1, p2
                    self.hl_propose(Line(v, np.dot(v, pn1.a)))
                else:
                    diacirc = Circle((pn1.a + pn2.c)/2, np.linalg.norm(pn1.a - pn2.c)/2)
                    touchpoint_cand = intersection_cc(diacirc, pn2)
                    if len(touchpoint_cand) < 2: return
                    i,touchpoint = min(
                        enumerate(touchpoint_cand),
                        key = lambda x: np.linalg.norm(x[1]-coor)
                    )
                    tangent_name = "tangent{}".format(i)
                    self.confirm = self.run_tool, tangent_name, p1, p2
                    self.hl_propose(
                        Point(touchpoint),
                        line_passing_np_points(touchpoint, pn1.a),
                    )
            elif p2 != p1 and not pn2.identical_to(pn1):
                l = line_passing_points(pn1, pn2)
                self.confirm = self.run_tool, "line", p1, p2
                self.drag = self.drag_angle_bisector, p1,pn1, p2,pn2
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
        self.hl_select(p,p1)

        p2,pn2 = self.coor_to_point(coor)
        if p2 is not None:
            if p2 == p1:
                self.confirm = self.run_tool, "line", p, p1
                self.hl_propose(line_passing_points(pn,pn1))
                return
            coor = pn2.a
            self.hl_select(p2)

        self.hl_add_helper((pn.a,pn1.a))

        if eps_identical(coor, pn.a): return
        self.hl_add_helper((pn.a, coor))
        self.hl_propose(self.angle_bisector(pn1.a, pn.a, coor))
        if p2 is not None:
            self.confirm = self.run_tool, "angle_bisector_int", p1,p,p2

    def drag_parallel(self, coor, p1, pn1):
        self.hl_select(p1)
        p2,pn2 = self.coor_to_point(coor)
        if p2 is None:
            self.hl_add_helper(line_passing_np_points(pn1.a, coor))
        elif p2 != p1 and not pn2.identical_to(pn1):
            ln = line_passing_points(pn1, pn2)
            self.hl_select(p2)
            self.hl_add_helper(ln)
            self.confirm_next = self.select_parallel, (p1,p2), ln.n

    def select_parallel(self, coor, line_def, normal_vec):
        self.hl_select(*line_def)

        p,pn = self.coor_to_point(coor)
        if p is None:
            new_l = Line(normal_vec, np.dot(normal_vec, coor))
            self.hl_propose(new_l)
            self.confirm = self.m_parallel, new_l, line_def
        else:
            self.hl_select(p)
            new_l = Line(normal_vec, np.dot(normal_vec, pn.a))
            self.hl_propose(new_l)
            self.confirm = self.run_tool, "paraline", *(line_def+(p,))

    def m_parallel(self, new_l, line_def):
        d, = self.run_tool("direction_of", *line_def, update = False)
        return self.run_m_tool("m_line_with_dir", new_l, d)

class ComboPerpLine(GTool):

    def update_basic(self, coor):
        obj,objn = self.coor_to_pl(coor)
        if obj is not None:
            self.hl_select(obj)
            if isinstance(objn, Point):
                self.confirm_next = self.update_point2, obj, objn
                self.drag = self.drag_perp, obj, objn
            else:
                self.confirm_next = self.select_perp, (obj,), objn.v

    def perp_bisector(self, p1, p2):
        v = p1 - p2
        return Line(v, np.dot(v, p1+p2)/2)

    def update_point2(self, coor, p1, pn1):
        self.hl_select(p1)

        p2,pn2 = self.coor_to_point(coor)
        if p2 is None:
            l = self.perp_bisector(pn1.a, coor)
            self.hl_add_helper((pn1.a, coor))
            self.hl_propose(l)
        elif p2 != p1 and not pn2.identical_to(pn1):
            self.hl_select(p2)
            l = self.perp_bisector(pn1.a, pn2.a)
            self.confirm = self.run_tool, "perp_bisector", p1, p2
            self.drag = self.drag_angle_bisector, p1,pn1, p2,pn2
            self.hl_add_helper((pn1.a, pn2.a))
            self.hl_propose(l)

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
        self.hl_select(p,p1)
        self.hl_add_helper((pn.a,pn1.a))

        p2,pn2 = self.coor_to_point(coor)
        if p2 is not None:
            if p2 == p1:
                self.confirm = self.run_tool, "perp_bisector", p, p1
                self.hl_propose(self.perp_bisector(pn.a, pn1.a))
                return
            coor = pn2.a
            self.hl_select(p2)

        if eps_identical(coor, pn.a): return
        self.hl_add_helper((pn.a, coor))
        self.hl_propose(self.angle_bisector(pn1.a, pn.a, coor))
        if p2 is not None:
            self.confirm = self.run_tool, "angle_bisector_ext", p1,p,p2

    def drag_perp(self, coor, p1, pn1):
        self.hl_select(p1)
        p2,pn2 = self.coor_to_point(coor)
        if p2 is None:
            l = line_passing_np_points(pn1.a, coor)
            self.hl_add_helper(l)
            self.hl_propose(Line(l.v, np.dot(l.v, coor)))
        elif p2 != p1 and not pn2.identical_to(pn1):
            self.hl_select(p2)
            l = line_passing_points(pn1, pn2)
            self.hl_add_helper(l)
            self.hl_propose(Line(l.v, np.dot(l.v, pn2.a)))
            self.confirm_next = self.select_perp, (p1,p2), l.v

    def select_perp(self, coor, line_def, normal_vec):
        self.hl_select(*line_def)
        p,pn = self.coor_to_point(coor)

        if p is None:
            new_l = Line(normal_vec, np.dot(normal_vec, coor))
            self.hl_propose(new_l)
            self.confirm = self.m_perpline, new_l, line_def
        else:
            self.hl_select(p)
            nl = Line(normal_vec, np.dot(normal_vec, pn.a))
            self.hl_propose(nl)
            self.confirm = self.run_tool, "perpline", *(line_def+(p,))

    def m_perpline(self, new_l, line_def):
        d, = self.run_tool("perp_direction", *line_def, update = False)
        return self.run_m_tool("m_line_with_dir", new_l, d)

class ComboCircle(GTool):

    def update_basic(self, coor):
        p,pn = self.coor_to_point(coor)
        if p is not None:
            self.hl_select(p)
            self.confirm_next = self.update_p, p, pn
            self.drag = self.drag_radius, p, pn

    def update_p(self, coor, center, center_n):
        p, pn = self.coor_to_point(coor)
        self.hl_select(center)
        if p is None:
            new_c = Circle(center_n.a, np.linalg.norm(center_n.a-coor))
            self.hl_propose(new_c)
            self.confirm = self.run_m_tool, "m_circle_with_center", new_c, center
        elif p != center and not pn.identical_to(center_n):
            self.hl_select(p)
            new_c = Circle(center_n.a, np.linalg.norm(center_n.a-pn.a))
            self.hl_propose(new_c)
            self.confirm = self.run_tool, "circle", center, p

    def drag_radius(self, coor, p1, pn1):
        self.hl_select(p1)
        p2, pn2 = self.coor_to_point(coor)
        if p2 is not None and not pn2.identical_to(pn1):
            self.hl_select(p2)
            r = np.linalg.norm(pn2.a-pn1.a)
            new_c = Circle(pn2.a, r)
            self.hl_propose(new_c)
            self.confirm_next = self.update_center, p1,p2, (pn1.a,pn2.a), r
        elif not eps_identical(coor, pn1.a):
            c = Circle(coor, np.linalg.norm(coor-pn1.a))
            self.hl_propose(c)

    def update_center(self, coor, p1,p2, radius_helper, r):
        self.hl_select(p1,p2)
        self.hl_add_helper(radius_helper)
        center, center_n = self.coor_to_point(coor)
        if center is None:
            c = Circle(coor, r)
            self.hl_propose(c)
            self.confirm = self.m_compass, c, p1,p2
        else:
            self.hl_select(center)
            c = Circle(center_n.a, r)
            self.hl_propose(c)
            self.confirm = self.run_tool, "compass", p1,p2,center

    def m_compass(self, new_c, p1,p2):
        r, = self.run_tool("dist", p1, p2, update = False)
        return self.run_m_tool("m_circle_with_radius", new_c, r)

class ComboCircumCircle(GTool):

    def update_basic(self, coor):
        p1,pn1 = self.coor_to_point(coor)
        if p1 is not None:
            self.hl_select(p1)
            self.confirm_next = self.update_p, p1, pn1

    def update_p(self, coor, p1, pn1):
        self.hl_select(p1)
        p2,pn2 = self.coor_to_point(coor)
        if p2 is None:
            center = (pn1.a + coor)/2
            c = Circle(center, np.linalg.norm(center-coor))
            self.hl_propose(c)
            self.confirm = self.run_m_tool, "m_circle_passing1", c, p1
        elif p1 != p2 and not pn2.identical_to(pn1):
            self.hl_select(p2)
            center = (pn1.a + pn2.a)/2
            c = Circle(center, np.linalg.norm(center-pn2.a))
            self.hl_propose(c)
            self.confirm_next = self.update_pp, p1,pn1,p2,pn2

    def update_pp(self, coor, p1,pn1, p2,pn2):
        self.hl_select(p1,p2)
        p3,pn3 = self.coor_to_point(coor)
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
            self.hl_select(p3)
            c = circumcircle(pn1,pn2,pn3)
            self.confirm = self.run_tool, "circumcircle", p1,p2,p3

        if c is not None: self.hl_propose(c)
