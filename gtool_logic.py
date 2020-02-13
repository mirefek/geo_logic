from gtool import GTool
from primitive_pred import not_collinear
from primitive_constr import circumcircle
from geo_object import *
import itertools

class GToolReason(GTool):

    icon_name = "reason"
    key_shortcut = 'r'
    label = "Reasoning Tool"
    def order_angle(self,pn1,pn2,pn3, x,y):
        if np.linalg.det(np.stack([pn2.a-pn1.a, pn3.a-pn1.a])) <= 0:
            return x,y
        else: return y,x

    # . (X) Y A->B    = concyclic_to_angles
    # . (Y) X->Z      = inscribed_angle
    # . (X) w         = point_on_circle
    # . (A)->B X Y    = angles_to_concyclic
    # . (A)->B X w    = on_circle_by_angle
    # . (A)->B X l    = point_to_perp_bisector
    # . (A)->B l X    = point_on_perp_bisector
    # . (w) X         = point_to_circle
    # (w) A B C D   = eq_arcs_to_eq_dist
    # (w) A->B C->D = eq_dist_to_eq_arcs
    def update_basic(self, coor):
        p,pn = self.select_point(coor)
        if p is not None:
            self.confirm_next = self.update_p, p,pn
            self.drag = self.drag_p, p,pn
            return

        c,cn = self.select_circle(coor)
        if c is not None:
            self.confirm_next = self.update_c, c,cn

    # X (Y) A->B    = concyclic_to_angles
    # Y (X)->Z      = inscribed_angle
    # X (w)         = point_on_circle
    def update_p(self, coor, p1,pn1):
        p2,pn2 = self.select_point(coor)
        if p2 is not None:
            if pn2.identical_to(pn1): return
            self.confirm_next = self.update_pp, p1,pn1, p2,pn2
            self.drag = self.drag_pp, p1,pn1, p2,pn2
            return
        c,cn = self.select_circle(coor)
        if c is not None:
            self.confirm = self.run_tool, "point_on_circle", p1,c
            self.hl_add_helper((pn1.a, cn.c))

    # X Y (A)->B    = concyclic_to_angles
    def update_pp(self, coor, p1,pn1, p2,pn2):
        p3,pn3 = self.select_point(coor)
        if p3 is None: pn3 = Point(coor)
        elif not_collinear(pn1,pn2,pn3):
            self.drag = self.drag_ppp, p1,pn1, p2,pn2, p3,pn3
        if not_collinear(pn1,pn2,pn3):
            self.hl_add_helper(circumcircle(pn1,pn2,pn3), permanent = True)

    # X Y A->(B)    = concyclic_to_angles
    def drag_ppp(self, coor, p1,pn1, p2,pn2, p3,pn3):
        p4,pn4 = self.select_point(coor)
        if p4 is None: pn4 = Point(coor)
        else:
            a,b = self.order_angle(pn3,pn1,pn4, p3,p4)
            self.confirm = self.run_tool, "concyclic_to_angles", a,b,p1,p2

        i_points = enumerate(x.a for x in (pn1,pn2,pn3,pn4))
        for (i,x),(j,y) in itertools.combinations(i_points, 2):
            if (i,j) != (0,1): self.hl_add_helper((x,y))

    # X A->(B)    = inscribed angle
    def drag_pp(self, coor, p1,pn1, p2,pn2):
        p3,pn3 = self.select_point(coor)
        if p3 is None: pn3 = Point(coor)
        else:
            a,b = self.order_angle(pn2,pn1,pn3, p2,p3)
            self.confirm = self.run_tool, "inscribed_angle", a,p1,b

        if not_collinear(pn1,pn2,pn3):
            self.hl_add_helper(circumcircle(pn1,pn2,pn3))
        self.hl_add_helper(
            (pn1.a, pn2.a),
            (pn1.a, pn3.a),
        )

    # A->(B) X Y    = angles_to_concyclic
    # A->(B) X w    = on_circle_by_angle
    # A->(B) X l    = point_to_perp_bisector
    # A->(B) l X    = point_on_perp_bisector
    def drag_p(self, coor, p1,pn1):
        p2,pn2 = self.select_point(coor)
        if p2 is None: pn2 = Point(coor)
        elif not pn2.identical_to(pn1):
            self.confirm_next = self.update_s, (p1,p2),(pn1,pn2)
        self.hl_add_helper((pn1.a,pn2.a), permanent = True)

    # A->B (X) Y    = angles_to_concyclic
    # A->B (X) w    = on_circle_by_angle
    # A->B (X) l    = point_to_perp_bisector
    # A->B (l) X    = point_on_perp_bisector
    def update_s(self, coor, seg, segn):
        p3,pn3 = self.select_point(coor)
        if p3 is not None:
            if all(not pn.identical_to(pn3) for pn in segn):
                self.confirm_next = self.update_sp, seg,segn, p3,pn3
        else:
            l,ln = self.select_line(coor)
            if l is not None:
                self.confirm_next = self.update_sl, seg,segn, l,ln
                return
            else: pn3 = Point(coor)

        helpers = ((x.a,pn3.a) for x in segn)
        self.hl_add_helper(*helpers, permanent = True)
        if not_collinear(pn3, *segn):
            self.hl_add_helper(circumcircle(pn3, *segn))

    # A->B X (Y)    = angles_to_concyclic
    # A->B X (w)    = on_circle_by_angle
    # A->B X (l)    = point_to_perp_bisector
    def update_sp(self, coor, seg,segn, p3,pn3):
        pn1,pn2 = segn
        p4,pn4 = self.select_point(coor)
        if p4 is not None:
            if p4 != p3 and all(not pn.identical_to(p3) for pn in segn):
                a,b = self.order_angle(pn1,pn3,pn2, *seg)
                self.confirm = self.run_tool, "angles_to_concyclic", a,b,p3,p4
        else: pn4 = Point(coor)

        if p4 is None:
            cl,cln = self.select_cl(coor)
            if cl is not None:
                if isinstance(cln, Line):
                    self.confirm = self.run_tool, "point_to_perp_bisector", p3,cl,*seg
                else: self.confirm = self.run_tool, "on_circle_by_angle", p3,cl,*seg
                return

        helpers = ((x.a,pn4.a) for x in segn)
        self.hl_add_helper(*helpers)

    # A->B l (X)    = point_on_perp_bisector
    def update_sl(self, coor, seg,segn, l,ln):
        p,pn = self.select_point(coor)
        if p is not None:
            pn1,pn2 = segn
            a,b = self.order_angle(pn1,pn,pn2, *seg)
            self.confirm = self.run_tool, "point_on_perp_bisector", p,l,a,b

    # w (X)         = point_to_circle
    # w (A) B C D   = eq_arcs_to_eq_dist
    # w (A)->B C->D = eq_dist_to_eq_arcs
    def update_c(self, coor, c,cn):
        def filter_f(p,pn): return self.lies_on(p,c)
        p,pn = self.select_point(coor)
        if p is None: return
        if not filter_f(p,pn):
            self.confirm = self.run_tool, "point_to_circle", p,c
        else:
            pos = vector_direction(pn.a - cn.c)
            self.confirm = self.hl_selected.remove, c
            self.confirm_next = self.update_cp, c,cn, filter_f, pos,(c,p)
            self.drag = self.drag_cp, cn,filter_f, pn,(c,p)

    # w A (B) C D   = eq_arcs_to_eq_dist
    def update_cp(self, coor, c,cn, filter_f,pos1, args):
        p,pn = self.select_point(coor, filter_f = filter_f)
        if p is None:
            if eps_identical(cn.c, coor): return
            pn = Point(coor)
        pos2 = vector_direction(pn.a - cn.c)
        if eps_identical((pos1-pos2+1)%2, 1): return
        pos_arc = ((pos2-pos1) % 2) <= 1
        if pos_arc: self.hl_select((c, pos1, pos2), permanent = True)
        else: self.hl_select((c, pos2, pos1), permanent = True)
        if p is not None:
            self.confirm_next = self.update_cpp, c,cn, filter_f, pos_arc, args+(p,)
    # w A B (C) D   = eq_arcs_to_eq_dist
    def update_cpp(self, coor, c,cn, filter_f, pos_arc, args):
        p,pn = self.select_point(coor, filter_f = filter_f)
        if p is None: return
        pos = vector_direction(pn.a - cn.c)
        self.confirm = self.hl_selected.remove_if, lambda x: isinstance(x, tuple)
        self.confirm_next = self.update_cppp, c,cn, filter_f, pos, pos_arc, args+(p,)
    # w A B C (D)   = eq_arcs_to_eq_dist
    def update_cppp(self, coor, c,cn, filter_f, pos1, pos_arc, args):
        p4,pn4 = self.select_point(coor, filter_f = filter_f)
        if p4 is None:
            if eps_identical(cn.c, coor): return
            pn4 = Point(coor)
        pos2 = vector_direction(pn4.a - cn.c)
        if eps_identical((pos1-pos2+1)%2, 1): return
        if pos_arc: self.hl_select((c, pos1, pos2), permanent = True)
        else: self.hl_select((c, pos2, pos1), permanent = True)
        if p4 is not None:
            c,p1,p2,p3 = args
            if not pos_arc: p1,p2,p3,p4 = p2,p1,p4,p3
            self.confirm = self.run_tool, "eq_arcs_to_eq_dist", p1,p2,p3,p4,c

    # w A->(B) C->D = eq_dist_to_eq_arcs
    def drag_cp(self, coor, cn,filter_f, pn1, args):
        p2,pn2 = self.select_point(coor, filter_f = filter_f)
        if p2 is None: pn2 = Point(coor)
        elif pn2.identical_to(pn1): return
        self.hl_add_helper((pn1.a, pn2.a), permanent = True)
        if p2 is not None:
            self.confirm_next = self.update_cs, cn,filter_f, args+(p2,)
    # w A->B (C)->D = eq_dist_to_eq_arcs
    def update_cs(self, coor, cn,filter_f, args):
        p,pn = self.select_point(coor, filter_f = filter_f)
        if p is not None:
            self.drag = self.drag_csp, cn,filter_f, pn,args+(p,)
    # w A->B C->D = eq_dist_to_eq_arcs
    def drag_csp(self, coor, cn,filter_f, pn1, args):
        p2,pn2 = self.select_point(coor, filter_f = filter_f)
        if p2 is None: pn2 = Point(coor)
        elif pn2.identical_to(pn1): return
        self.hl_add_helper((pn1.a, pn2.a))
        if p2 is not None:
            self.confirm = self.confirm_eq_arcs_by_dist, *args+(p2,)
    # w A->B C->D = (eq_dist_to_eq_arcs)
    def confirm_eq_arcs_by_dist(self, c,p1,p2,p3,p4):
        cn,pn1,pn2 = map(self.env.gi_to_num, (c,p1,p2))
        pos1,pos2 = (
            vector_direction(pn.a - cn.c) for pn in (pn1,pn2)
        )
        pos_arc = ((pos2-pos1) % 2) <= 1
        print(pos1, pos2)
        if not pos_arc:
            p1,p2 = p2,p1
            p3,p4 = p4,p3
        self.run_tool("eq_dist_to_eq_arcs", p1,p2,p3,p4,c)
