from relstr import RelStr
from stop_watch import StopWatch
from geo_object import *

# general class for triggers, can be also used as "dummy triggers" not doing anything
class RelStrEnv:
    def __init__(self, logic):
        self.logic = logic
        self.num_model = logic.num_model
        self.relstr = RelStr()
        self.to_run = []
        self.discarded = set()
        self.running = False

    # when a new relation is added to the RelStr (lookup table)
    # t = label, data = input + output
    def add(self, t, data):
        pass

    # run all actions accumulated so far
    def run(self):
        if self.running: return
        self.running = True
        while self.to_run:
            action, x_to_y = self.to_run.pop()
            if any(y in self.discarded for y in x_to_y): continue
            action(x_to_y)
        self.running = False

    def discard_node(self, n, store_disc_edges = None):
        self.discarded.add(n)
        self.relstr.discard_node(n, store_disc_edges)

    def glue_nodes(self, glue_dict):
        disc_edges = []
        for src in glue_dict.keys(): self.discard_node(src, disc_edges)
        for t,data in disc_edges:
            self.add(t, tuple(glue_dict.get(x, x) for x in data))

"""
Triggers automatically call the following "axioms" whenever possible:

intersection_uq_ll a:L b:L X:P Y:P ->
  <- not_eq a b
  <- lies_on X a
  <- lies_on X b
  <- lies_on Y a
  <- lies_on Y b
  THEN
  <- == X Y
intersection_uq_lc a:L b:C X:P Y:P ->
  <- intersecting a b
  <- lies_on X a
  <- lies_on X b
  <- lies_on Y a
  <- lies_on Y b
  Z <- intersection_remoter a b X
  <- not_eq Y Z
  THEN
  <- == X Y
intersection_uq_cc a:C b:C X:P Y:P ->
  <- intersecting a b
  <- lies_on X a
  <- lies_on X b
  <- lies_on Y a
  <- lies_on Y b
  Z <- intersection_remoter a b X
  <- not_eq Y Z
  THEN
  <- == X Y
line_uq_pp X:P Y:P a:L b:L ->
  <- not_eq X Y
  <- lies_on X a
  <- lies_on X b
  <- lies_on Y a
  <- lies_on Y b
  THEN
  <- == a b
line_uq_pd X:P a:L b:L ->
  da <- direction_of a
  db <- direction_of b
  <- == da db
  <- lies_on X a
  <- lies_on X b
  THEN
  <- == a b
circle_cr_uq w:C r:D O:P ->
  rw <- radius_of w
  Ow <- center_of O
  <- == rw r
  <- == Ow O
  THEN
  c2 <- circle O r
  <- == c c2
circumcircle_uq A:P B:P C:P a:C b:C ->
  <- lies_on A a
  <- lies_on B a
  <- lies_on C a
  <- lies_on A b
  <- lies_on B b
  <- lies_on C b
  <- not_eq A B
  <- not_eq B C
  <- not_eq C A
  THEN
  <- == a b
"""
class TriggerEnv(RelStrEnv):
    # intersection_uq_ll
    # intersection_uq_lc, not tangent
    # intersection_uq_cc, not tangent
    # line_uq_pp
    # line_uq_pd
    # circle_cr_uq
    # circumcircle_uq
    def __init__(self, rel_names, logic):

        RelStrEnv.__init__(self, logic)

        self.lies_on_l = rel_names.lies_on_l
        self.lies_on_c = rel_names.lies_on_c
        self.direction_of = rel_names.direction_of
        self.radius_of = rel_names.radius_of
        self.center_of = rel_names.center_of
        self.circle = rel_names.circle

        self.label_to_action = {
            self.lies_on_l    : self.lies_on_l_added,
            self.lies_on_c    : self.lies_on_c_added,
            self.direction_of : self.direction_of_added,
            self.radius_of    : self.radius_of_added,
            self.center_of    : self.center_of_added,
        }

    def add(self, t, data):
        if t not in self.label_to_action: return
        if self.relstr.add_rel(t, data):
            self.label_to_action[t](*data)

    def glue_trig(self, pair):
        a,b = pair
        self.logic.glue(a,b)

    def add_circ_trig(self, Orc):
        O,r,c = Orc

        c2_tup = self.logic.get_constr(self.circle, (O, r))
        if c2_tup is None:
            self.logic.add_constr(self.circle, (O, r), (c,))
        else:
            c2, = c2_tup
            if c2 != c: self.glue_trig(self.glue_trig, (c, c2))

    def num_equal(self, a, b):
        return self.num_model[a].identical_to(self.num_model[b])

    def lies_on_l_added(self, p, l):

        # line_uq_pp
        # intersection_uq_ll
        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        passing_l = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing_c = self.relstr.tobj_to_nb[self.lies_on_c,p,0]

        if len(points) < len(passing_l):
            for p2,_ in points:
                if p2 != p: self.ppll_search_ppl(p, p2, l)
        else:
            for _,l2 in passing_l:
                if l2 != l: self.ppll_search_pll(p, l, l2)

        # intersection_uq_lc
        if len(points) <= len(passing_c):
            for p2,_ in points:
                if p2 != p:
                    self.intersection_uq_c_search_ppl(p, p2, l)
        else:
            for _,c in passing_c:
                self.intersection_uq_c_search_pcl(p, c, l)

        # line_uq_pd
        d_tup = self.logic.get_constr(self.direction_of, (l,))
        if d_tup is not None:
            d, = d_tup
            self.line_uq_pd_search_pld(p,l,d)

    def lies_on_c_added(self, p, c):

        points = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        passing_l = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing_c = self.relstr.tobj_to_nb[self.lies_on_c,p,0]

        # intersection_uq_cc, not tangent
        # intersection_uq_lc, not tangent
        if len(points) <= len(passing_c) + len(passing_l):
            for p2,_ in points:
                if p2 != p:
                    self.intersection_uq_c_search_ppc(p, p2, c) # DONE
        else:
            for _,l in passing_l:
                self.intersection_uq_c_search_pcl(p, c, l) # DONE
            for _,c2 in passing_c:
                if c2 != c:
                    self.intersection_uq_c_search_pcc(p, c, c2) # DONE

        # circumcircle_uq
        if len(points) >= 3:
            for _,c2 in passing_c:
                if c != c2 and self.num_equal(c, c2):
                    self.circumcircle_uq_search(c,c2)

    def direction_of_added(self, l, d):  # search for line_uq_pd

        parallel = self.relstr.tobj_to_nb[self.direction_of,d,1]
        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]

        if (len(parallel) <= len(points)):
            for l2,_ in parallel:
                if l != l2 and self.num_equal(l, l2):
                    self.line_uq_pd_search_lld(l, l2, d)

        else:
            for p,_ in points:
                self.line_uq_pd_search_pld(p, l, d)

    def radius_of_added(self, c, r):
        # circle_cr_uq
        O_tup = self.logic.get_constr(self.center_of, (c,))
        if O_tup is None: return
        O, = O_tup
        self.to_run.append((self.add_circ_trig, (O, r, c)))

    def center_of_added(self, c, O):
        # circle_cr_uq
        r_tup = self.logic.get_constr(self.radius_of, (c,))
        if r_tup is None: return
        r, = r_tup
        self.to_run.append((self.add_circ_trig, (O, r, c)))

    # -------------------------------------
    # search scripts

    def ppll_search_ppl(self, p, p2, l):
        passing = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_l,p2,0]
        if len(passing2) < len(passing):
            passing, passing2 = passing2, passing
            p,p2 = p2,p
        for _,l2 in passing:
            if l != l2 and (p2,l2) in passing2:
                if not self.num_equal(p, p2):
                    assert(self.num_equal(l, l2))
                    self.to_run.append((self.glue_trig, (l, l2)))
                    # if there was other line l3 passing through p, p2
                    # we would already know l2 == l3
                    break
                if not self.num_equal(l, l2):
                    assert(self.num_equal(p, p2))
                    self.to_run.append((self.glue_trig, (p, p2)))
                    break # l2 is just a witness

    def ppll_search_pll(self, p, l, l2):
        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_l,l2,1]
        if len(points2) < len(points):
            points, points2 = points2, points
            l,l2 = l2,l
        for p2,_ in points:
            if p2 != p and (p2,l2) in points2:
                if not self.num_equal(p, p2):
                    assert(self.num_equal(l, l2))
                    self.to_run.append((self.glue_trig, (l, l2)))
                    break # p2 is lust a witness
                if not self.num_equal(l, l2):
                    assert(self.num_equal(p, p2))
                    self.to_run.append((self.glue_trig, (p, p2)))
                    # if there was other point p3 in the intersection of l and l2,
                    # we would already know p2 == p3
                    break

    def intersection_uq_c_search_ppl(self, p, p2, l):
        if not self.num_equal(p2, p): return
        passing = self.relstr.tobj_to_nb[self.lies_on_c,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_c,p2,0]
        if len(passing2) < len(passing):
            passing,passing2 = passing2,passing
            p,p2 = p2,p
        for _,c in passing:
            if (p2,c) in passing2 and intersecting_lc(self.num_model[l], self.num_model[c]):
                self.to_run.append((self.glue_trig, (p, p2)))
                break # c is just a witness

    def intersection_uq_c_search_ppc(self, p, p2, c):
        
        if not self.num_equal(p2, p): return

        # lines
        passing = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_l,p2,0]
        if len(passing2) < len(passing):
            passing,passing2 = passing2,passing
            p,p2 = p2,p
        for _,l in passing:
            if (p2,l) in passing2 and intersecting_lc(self.num_model[l], self.num_model[c]):
                self.to_run.append((self.glue_trig, (p, p2)))
                return # l is just a witness

        # circles
        passing = self.relstr.tobj_to_nb[self.lies_on_c,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_c,p2,0]
        if len(passing2) < len(passing):
            passing,passing2 = passing2,passing
            p,p2 = p2,p
        for _,c2 in passing:
            if (p2,c2) in passing2 and intersecting_cc(self.num_model[c], self.num_model[c2]):
                assert(self.num_equal(p, p2))
                self.to_run.append((self.glue_trig, (p, p2)))
                return # c2 is just a witness

    def intersection_uq_c_search_pcl(self, p, c, l):

        if not intersecting_lc(self.num_model[l], self.num_model[c]): return
        points_l = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        points_c = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        if len(points_l) < len(points_c):
            points = points_l
            points2 = points_c
            lc2 = c
        else:
            points = points_c
            points2 = points_l
            lc2 = l
        for p2,_ in points:
            if p2 != p and (p2,lc2) in points2 and self.num_equal(p, p2):
                self.to_run.append((self.glue_trig, (p, p2)))
                # if there was other point p3 in the intersection of l and c,
                # we would already know p2 == p3
                break

    def intersection_uq_c_search_pcc(self, p, c, c2):

        if not intersecting_cc(self.num_model[c], self.num_model[c2]): return
        points = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_c,c2,1]
        if len(points2) < len(points):
            points, points2 = points2, points
            c,c2 = c2,c
        for p2,_ in points:
            if p2 != p and (p2,c2) in points2 and (self.num_equal(p, p2)):
                self.to_run.append((self.glue_trig, (p, p2)))
                # if there was other point p3 in the intersection of c and c2,
                # we would already know p2 == p3
                break

    def circumcircle_uq_search(self, c,c2):

        points = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_c,c2,1]
        if len(points2) < len(points):
            c,c2 = c2,c
            points,points2 = points2,points
        witnesses = []
        for p,_ in points:
            if (p,c2) in points2 and not any(
                self.num_equal(w, p)
                for w in witnesses
            ):
                witnesses.append(p)
                if len(witnesses) >= 3:
                    assert(self.num_equal(c, c2))
                    self.to_run.append((self.glue_trig, (c, c2)))
                    break

    def line_uq_pd_search_lld(self, l, l2, d):

        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_l,l2,1]
        if len(points2) < len(points):
            l,l2 = l2,l
            points,points2 = points2,points
        for p,_ in points:
            if (p,l2) in points2:
                assert(self.num_equal(l, l2))
                self.to_run.append((self.glue_trig, (l, l2)))
                break # p is just a witness

    def line_uq_pd_search_pld(self, p, l, d):

        parallel = self.relstr.tobj_to_nb[self.direction_of,d,1]
        passing = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        if len(parallel) < len(passing):
            for l2,_ in parallel:
                if l2 != l and (p,l2) in passing:
                    assert(self.num_equal(l, l2))
                    self.to_run.append((self.glue_trig, (l, l2)))
                    # if other parallel passing line l3 was equal to l,
                    # we would already know l2 == l3
                    break

        else:
            for _,l2 in passing:
                if l2 != l and (l2,d) in parallel:
                    assert(self.num_equal(l, l2))
                    self.to_run.append((self.glue_trig, (l, l2)))
                    # if other parallel passing line l3 was equal to l,
                    # we would already know l2 == l3
                    break
