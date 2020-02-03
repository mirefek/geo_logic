from relstr import RelStr
from stop_watch import StopWatch
from geo_object import *

class RelStrEnv:
    def __init__(self, model):
        self.model = model
        self.num_model = model.num_model
        self.relstr = RelStr()
        self.to_run = []
        self.discarded = set()
        self.running = False

    def add(self, t, data):
        pass

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

class ImportedTools:
    def __init__(self, tool_dict):
        self.lies_on_l = tool_dict['lies_on', (Point, Line)]
        self.lies_on_c = tool_dict['lies_on', (Point, Circle)]
        self.direction_of = tool_dict['direction_of', (Line,)]
        self.radius_of = tool_dict['radius_of', (Circle,)]
        self.center_of = tool_dict['center_of', (Circle,)]
        self.circle = tool_dict['circle', (Point, Ratio)]
        self.dist = tool_dict['dist', (Point, Point)]
        self.arc_length = tool_dict.get(('arc_length', (Point, Point, Circle)), None)

class TriggerEnv(RelStrEnv):
    # intersection_uq_ll
    # intersection_uq_lc, not tangent
    # intersection_uq_cc, not tangent
    # line_uq_pp
    # line_uq_pd
    # circle_cr_uq
    # circumcircle_uq
    def __init__(self, rel_names, model):

        RelStrEnv.__init__(self, model)
        
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
        #print("--- GLUE", self.model.obj_types[a].__name__, a, self.model.obj_types[b].__name__, b)
        self.model.glue(a,b)

    def add_circ_trig(self, Orc):
        O,r,c = Orc

        c2_tup = self.model.get_constr(self.circle, (O, r))
        if c2_tup is None:
            #print("--- NEW CIRCLE", O, r, c)
            self.model.add_constr(self.circle, (O, r), (c,))
        else:
            c2, = c2_tup
            if c2 != c: self.glue_trig(self.glue_trig, (c, c2))

    def num_equal(self, a, b):
        return self.num_model[a].identical_to(self.num_model[b])

    def lies_on_l_added(self, p, l):

        #print("added: lies_on_l", p, l) # DONE

        # line_uq_pp
        # intersection_uq_ll
        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        passing_l = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing_c = self.relstr.tobj_to_nb[self.lies_on_c,p,0]

        if len(points) < len(passing_l):
            #print('  case points < passing_l') # DONE
            for p2,_ in points:
                if p2 != p: self.ppll_search_ppl(p, p2, l)
        else:
            #print('  case points >= passing_l') # DONE
            for _,l2 in passing_l:
                if l2 != l: self.ppll_search_pll(p, l, l2)

        # intersection_uq_lc
        if len(points) <= len(passing_c):
            #print('  case points <= passing_c') # DONE
            for p2,_ in points:
                if p2 != p:
                    self.intersection_uq_c_search_ppl(p, p2, l)
        else:
            #print('  case points > passing_c') # DONE
            for _,c in passing_c:
                self.intersection_uq_c_search_pcl(p, c, l)

        # line_uq_pd
        #print('  checking directions') # DONE
        d_tup = self.model.get_constr(self.direction_of, (l,))
        if d_tup is not None:
            d, = d_tup
            self.line_uq_pd_search_pld(p,l,d)
        #print('lies_on_l DONE')

    def lies_on_c_added(self, p, c):
        #print("added: lies_on_c", p, c)

        points = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        passing_l = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing_c = self.relstr.tobj_to_nb[self.lies_on_c,p,0]

        # intersection_uq_cc, not tangent
        # intersection_uq_lc, not tangent
        if len(points) <= len(passing_c) + len(passing_l):
            #print('  case points <= passing_l + passing_c') # DONE
            for p2,_ in points:
                if p2 != p:
                    self.intersection_uq_c_search_ppc(p, p2, c) # DONE
        else:
            #print('  case points > passing_l + passing_c') # DONE
            for _,l in passing_l:
                self.intersection_uq_c_search_pcl(p, c, l) # DONE
            for _,c2 in passing_c:
                if c2 != c:
                    self.intersection_uq_c_search_pcc(p, c, c2) # DONE

        # circumcircle_uq
        if len(points) >= 3:
            #print('  checking circumcircles')
            for _,c2 in passing_c:
                if c != c2 and self.num_equal(c, c2):
                    self.circumcircle_uq_search(c,c2)
        #print('lies_on_l DONE')

    def direction_of_added(self, l, d):  # search for line_uq_pd
        #print("added: direction_of", l, d) # DONE

        parallel = self.relstr.tobj_to_nb[self.direction_of,d,1]
        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]

        if (len(parallel) <= len(points)):
            #print('  case parallel <= points') # DONE
            for l2,_ in parallel:
                if l != l2 and self.num_equal(l, l2):
                    self.line_uq_pd_search_lld(l, l2, d)

        else:
            #print('  case parallel > points') # DONE
            for p,_ in points:
                self.line_uq_pd_search_pld(p, l, d)
        #print('direction_of DONE')

    def radius_of_added(self, c, r):
        #print("radius_of_added", c, r) # DONE
        # circle_cr_uq
        O_tup = self.model.get_constr(self.center_of, (c,))
        if O_tup is None: return
        O, = O_tup
        #print('  TRIGGERED: add_circ_trig') # DONE
        self.to_run.append((self.add_circ_trig, (O, r, c)))

    def center_of_added(self, c, O):
        #print("center_of_added", c, O) # DONE
        # circle_cr_uq
        r_tup = self.model.get_constr(self.radius_of, (c,))
        if r_tup is None: return
        r, = r_tup
        #print('  TRIGGERED: add_circ_trig') # DONE
        self.to_run.append((self.add_circ_trig, (O, r, c)))

    # -------------------------------------
    # search scripts

    def ppll_search_ppl(self, p, p2, l):
        #print('    ppll_search_ppl') # DONE
        passing = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_l,p2,0]
        if len(passing2) < len(passing):
            #print('      swap passing passing2') # DONE
            passing, passing2 = passing2, passing
            p,p2 = p2,p
        for _,l2 in passing:
            if l != l2 and (p2,l2) in passing2:
                if not self.num_equal(p, p2):
                    assert(self.num_equal(l, l2))
                    #print('      TRIGGERED: glue lines') # DONE
                    self.to_run.append((self.glue_trig, (l, l2)))
                    # if there was other line l3 passing through p, p2
                    # we would already know l2 == l3
                    break
                if not self.num_equal(l, l2):
                    assert(self.num_equal(p, p2))
                    #print('      TRIGGERED: glue points') # DONE
                    self.to_run.append((self.glue_trig, (p, p2)))
                    break # l2 is just a witness

    def ppll_search_pll(self, p, l, l2):
        #print('    ppll_search_pll') # DONE
        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_l,l2,1]
        if len(points2) < len(points):
            #print('      swap points points2') # DONE
            points, points2 = points2, points
            l,l2 = l2,l
        for p2,_ in points:
            if p2 != p and (p2,l2) in points2:
                if not self.num_equal(p, p2):
                    assert(self.num_equal(l, l2))
                    #print('      TRIGGERED: glue lines') # DONE
                    self.to_run.append((self.glue_trig, (l, l2)))
                    break # p2 is lust a witness
                if not self.num_equal(l, l2):
                    assert(self.num_equal(p, p2))
                    #print('      TRIGGERED: glue points') # DONE
                    self.to_run.append((self.glue_trig, (p, p2)))
                    # if there was other point p3 in the intersection of l and l2,
                    # we would already know p2 == p3
                    break

    def intersection_uq_c_search_ppl(self, p, p2, l):
        #print('    intersection_uq_c_search_pll')
        if not self.num_equal(p2, p): return
        passing = self.relstr.tobj_to_nb[self.lies_on_c,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_c,p2,0]
        if len(passing2) < len(passing):
            #print('      swap passing passing2')
            passing,passing2 = passing2,passing
            p,p2 = p2,p
        for _,c in passing:
            if (p2,c) in passing2 and intersecting_lc(self.num_model[l], self.num_model[c]):
                #print('      TRIGGERED: glue points')
                self.to_run.append((self.glue_trig, (p, p2)))
                break # c is just a witness

    def intersection_uq_c_search_ppc(self, p, p2, c):
        
        #print("    intersection_uq_c_search_ppc") # DONE
        if not self.num_equal(p2, p): return

        #print("    check lines") # DONE
        # lines
        passing = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_l,p2,0]
        if len(passing2) < len(passing):
            #print('      swap passing passing2') # DONE
            passing,passing2 = passing2,passing
            p,p2 = p2,p
        for _,l in passing:
            if (p2,l) in passing2 and intersecting_lc(self.num_model[l], self.num_model[c]):
                #print('      TRIGGERED: glue points') # DONE
                self.to_run.append((self.glue_trig, (p, p2)))
                return # l is just a witness

        #print("    check circles") # DONE
        # circles
        passing = self.relstr.tobj_to_nb[self.lies_on_c,p,0]
        passing2 = self.relstr.tobj_to_nb[self.lies_on_c,p2,0]
        if len(passing2) < len(passing):
            #print('      swap passing passing2') # DONE
            passing,passing2 = passing2,passing
            p,p2 = p2,p
        for _,c2 in passing:
            if (p2,c2) in passing2 and intersecting_cc(self.num_model[c], self.num_model[c2]):
                assert(self.num_equal(p, p2))
                #print('      TRIGGERED: glue points') # DONE
                self.to_run.append((self.glue_trig, (p, p2)))
                return # c2 is just a witness

    def intersection_uq_c_search_pcl(self, p, c, l):
        #print("    intersection_uq_c_search_pcl")

        if not intersecting_lc(self.num_model[l], self.num_model[c]): return
        points_l = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        points_c = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        if len(points_l) < len(points_c):
            #print("      case points_l < points_c") # DONE
            points = points_l
            points2 = points_c
            lc2 = c
        else:
            #print("      case points_l >= points_c") # DONE
            points = points_c
            points2 = points_l
            lc2 = l
        for p2,_ in points:
            if p2 != p and (p2,lc2) in points2 and self.num_equal(p, p2):
                #print('      TRIGGERED: glue points') # DONE
                self.to_run.append((self.glue_trig, (p, p2)))
                # if there was other point p3 in the intersection of l and c,
                # we would already know p2 == p3
                break

    def intersection_uq_c_search_pcc(self, p, c, c2):
        #print("    intersection_uq_c_search_pcc") # DONE

        if not intersecting_cc(self.num_model[c], self.num_model[c2]): return
        points = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_c,c2,1]
        if len(points2) < len(points):
            #print('      swap points points2') # DONE
            points, points2 = points2, points
            c,c2 = c2,c
        for p2,_ in points:
            if p2 != p and (p2,c2) in points2 and (self.num_equal(p, p2)):
                #print('      TRIGGERED: glue points') # DONE
                self.to_run.append((self.glue_trig, (p, p2)))
                # if there was other point p3 in the intersection of c and c2,
                # we would already know p2 == p3
                break

    def circumcircle_uq_search(self, c,c2):
        #print("    circumcircle_uq_search")

        points = self.relstr.tobj_to_nb[self.lies_on_c,c,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_c,c2,1]
        if len(points2) < len(points):
            #print('      swap points points2')
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
                    #print('      TRIGGERED: glue circles')
                    assert(self.num_equal(c, c2))
                    self.to_run.append((self.glue_trig, (c, c2)))
                    break

    def line_uq_pd_search_lld(self, l, l2, d):
        #print("    line_uq_pd_search_lld") # DONE

        points = self.relstr.tobj_to_nb[self.lies_on_l,l,1]
        points2 = self.relstr.tobj_to_nb[self.lies_on_l,l2,1]
        if len(points2) < len(points):
            #print("      swap points points2") # DONE
            l,l2 = l2,l
            points,points2 = points2,points
        for p,_ in points:
            if (p,l2) in points2:
                assert(self.num_equal(l, l2))
                #print("      TRIGGERED glue lines") # DONE
                self.to_run.append((self.glue_trig, (l, l2)))
                break # p is just a witness

    def line_uq_pd_search_pld(self, p, l, d):
        #print("    line_uq_pd_search_pld")

        parallel = self.relstr.tobj_to_nb[self.direction_of,d,1]
        passing = self.relstr.tobj_to_nb[self.lies_on_l,p,0]
        if len(parallel) < len(passing):
            #print("      case parallel < passing") # DONE
            for l2,_ in parallel:
                if l2 != l and (p,l2) in passing:
                    assert(self.num_equal(l, l2))
                    #print("      TRIGGERED glue lines") # DONE
                    self.to_run.append((self.glue_trig, (l, l2)))
                    # if other parallel passing line l3 was equal to l,
                    # we would already know l2 == l3
                    break

        else:
            #print("      case parallel >= passing") # DONE
            for _,l2 in passing:
                if l2 != l and (l2,d) in parallel:
                    assert(self.num_equal(l, l2))
                    #print("      TRIGGERED glue lines") # DONE
                    self.to_run.append((self.glue_trig, (l, l2)))
                    # if other parallel passing line l3 was equal to l,
                    # we would already know l2 == l3
                    break
