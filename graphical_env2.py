from tool_step import ToolStepEnv, proof_checker
from logic_model import LogicModel
import geo_object
from geo_object import *
import itertools
from collections import defaultdict
from tools import ToolError, ToolErrorException, MovableTool

def distribute_segments(segments, lev_zero_points = ()):
    segments.sort(key = lambda x: (x[0], -x[1]))
    lev_zero_points = sorted(lev_zero_points, reverse = True)
    occupied = [None]
    for a,b,start,info in segments:
        while lev_zero_points and not eps_smaller(a, lev_zero_points[-1]):
            lev_zero_points.pop()
        if lev_zero_points and eps_smaller(lev_zero_points[-1], b) and start == 0:
            start = 1
        for lev,b_ori in enumerate(occupied):
            if lev < start: continue
            if b_ori is None or not eps_smaller(a, b_ori):
                occupied[lev] = b
                break
        else:
            lev = len(occupied)
            occupied.append(b)
        yield info,lev

# (a,b,info), a in (0,2), b in (0,4), cyc mod 2
def distribute_segments_cyc(segments, lev_zero_points = ()):
    segments.sort(key = lambda x: (x[0], -x[1]))
    lev_zero_points = list(lev_zero_points) + [x+2 for x in lev_zero_points]
    lev_zero_points.sort(reverse = True)
    occupied = [(None,None)]
    for a,b,start,info in segments:
        while lev_zero_points and not eps_smaller(a, lev_zero_points[-1]):
            lev_zero_points.pop()
        if lev_zero_points and eps_smaller(lev_zero_points[-1], b) and start == 0:
            start = 1
        for lev,(a_ori,b_ori) in enumerate(occupied):
            if lev < start: continue
            if a_ori is None or (not eps_smaller(a, b_ori) and not eps_smaller(a_ori, b-2)):
                if a_ori is None: a_ori = a
                occupied[lev] = a_ori,b
                break
        else:
            lev = len(occupied)
            occupied.append((a,b))
        yield info,lev

class NumPointData:
    def __init__(self, env, point):
        self.env = env
        self.point = point
        self.active_candidates = []
        self.visible = None

    def add_active_candidate(self, li, priority):
        self.active_candidates.append((priority, li))
    def select_visible(self):
        if self.active_candidates:
            _,self.visible = max(self.active_candidates)
        return self.visible

class NumLineData:
    def __init__(self, env, line):
        self.env = env
        self.line = line
        self.active_candidates = []
        self.extra_candidates = []
        self.visible = None
        self.is_active = False
        self.dists = []

    def add_active_candidate(self, li, priority):
        self.is_active = True
        self.active_candidates.append((priority, li))
    def add_extra_candidate(self, li, priority):
        self.extra_candidates.append((priority, li))
    def select_visible(self):
        if self.is_active:
            _,self.visible = max(self.active_candidates)
        elif self.extra_candidates:
            _,self.visible = max(self.extra_candidates)
        return self.visible

    def add_dist(self, la,lb, na,nb, col):
        self.dists.append((la,lb,na,nb,col))
    def distribute_dists(self):
        if self.visible is None: points = ()
        else: points = self.env.line_to_points[self.visible]
        #print("POINTS", points, "ON", self.visible)

        segments = []
        for la,lb,na,nb,col in self.dists:
            if self.visible is None:
                start = 0
            elif la in points and lb in points:
                start = 0
            else: start = 1
            pos_a = np.dot(self.line.v, na)
            pos_b = np.dot(self.line.v, nb)
            if pos_a < pos_b: segments.append((pos_a, pos_b, start, (na,nb,pos_a,pos_b,col)))
            else: segments.append((pos_b, pos_a, start, (nb,na,pos_b,pos_a,col)))

        point_pos = [np.dot(self.line.v, self.env.li_to_num(p).a) for p in points]
        dists_lev = tuple(distribute_segments(segments, point_pos))
        if len(points) <= 1:
            self.colorization = None
            self.env.visible_dists.extend(
                (a,b,col,lev)
                for (a,b,_,_,col),lev in dists_lev
            )
        else:
            if self.is_active:
                active_positions = tuple(
                    np.dot(self.line.v, self.env.li_to_num(p).a)
                    for p in points
                )
                start_pos = min(active_positions)
                end_pos = max(active_positions)

            self.colorization = []
            cur_pos = None
            for (a,b,pos_a,pos_b,col),lev in dists_lev:
                if lev == 0:
                    if cur_pos is None:
                        if self.is_active:
                            self.colorization.append((None, start_pos, -2))
                            if start_pos < pos_a: self.colorization.append((start_pos, pos_a, -1))
                        else: self.colorization.append((None, pos_a, -2))
                    elif cur_pos < pos_a:
                        self.colorization.append((cur_pos, pos_a, -2))
                    self.colorization.append((pos_a,pos_b, col))
                    cur_pos = pos_b
                else: self.env.visible_dists.append((a,b,col,lev))
            if cur_pos is None:
                if self.is_active:
                    self.colorization = [
                        (None, start_pos, -2),
                        (start_pos, end_pos, -1),
                        (end_pos, None, -2),
                    ]
                else: self.colorization = None
            else:
                if self.is_active:
                    if cur_pos < end_pos:
                        self.colorization.append((cur_pos,end_pos, -1))
                    self.colorization.append((end_pos,None, -2))
                else: self.colorization.append((cur_pos,None, -2))

class NumCircleData:
    def __init__(self, env, circle):
        self.env = env
        self.circle = circle
        self.active_candidates = []
        self.extra_candidates = []
        self.is_active = False
        self.visible = None

    def add_active_candidate(self, li, priority):
        self.is_active = True
        self.active_candidates.append((priority, li))
    def add_extra_candidate(self, li, priority):
        self.extra_candidates.append((priority, li))
    def select_visible(self):
        if self.active_candidates:
            _,self.visible = max(self.active_candidates)
        elif self.extra_candidates:
            _,self.visible = max(self.extra_candidates)
        return self.visible

    def distribute_arcs(self):
        if self.visible is None: return
        points = self.env.circle_to_points[self.visible]
        if len(points) <= 1:
            self.colorization = None
            return

        arcs = self.env.circle_to_arcs[self.visible]
        point_to_pos = dict(
            (li, vector_direction(self.env.li_to_num(li).a
                                  - self.circle.c)%2)
            for li in points
        )
        segments = []
        for a,b,col in arcs:
            pos_a = point_to_pos.get(a, None)
            if a is None: continue
            pos_b = point_to_pos.get(b, None)
            if b is None: continue
            if pos_b < pos_a: pos_b += 2
            start = 0
            segments.append((pos_a, pos_b, start, (pos_a,pos_b,col)))
        arc_lev = tuple(distribute_segments_cyc(segments, point_to_pos.values()))

        positions = sorted(point_to_pos.values())

        out_start = None
        out_end = None
        if self.is_active:
            circ_color = -1
            if eps_bigger(positions[0]+1, positions[-1]):
                out_start = positions[-1]
                out_end = positions[0]
            else:
                for pos_a, pos_b in zip(positions, positions[1:]):
                    if eps_bigger(pos_b, pos_a+1):
                        out_start = pos_a
                        out_end = pos_b
                        break
        else: circ_color = -2

        def arc_tuple(a, b, *args):
            if a <= b: return (a,b,*args)
            else: return (a,b+2,*args)

        self.colorization = []
        def add_black_arc(pos_a, pos_b):
            if eps_identical(pos_a, pos_b): return
            #print("ADD_BLACK", pos_a, pos_b)
            #print("OUTSIDE", out_start, out_end)
            if out_start is not None and eps_bigger((pos_b-pos_a)%2, 1):
                #print("  outside")
                if not eps_identical(pos_a, out_start): self.colorization.append(arc_tuple(pos_a, out_start, -1))
                self.colorization.append(arc_tuple(out_start, out_end, -2))
                if not eps_identical(out_end, pos_b): self.colorization.append(arc_tuple(out_end, pos_b, -1))
            else:
                #print("  inside")
                self.colorization.append(arc_tuple(pos_a, pos_b, circ_color))

        cur_pos = None
        for (pos_a, pos_b, col), lev in arc_lev:
            if lev == 0:
                if cur_pos is not None:
                    add_black_arc(cur_pos, pos_a)
                else: first_pos = pos_a
                cur_pos = pos_b
                self.colorization.append(arc_tuple(pos_a, pos_b, col))
            else: self.env.visible_arcs.append(
                    arc_tuple(pos_a, pos_b, self.circle, col, lev)
            )

        if cur_pos is None:
            if out_start is None: self.colorization = None
            else: self.colorization = [
                arc_tuple(out_start, out_end, -2),
                arc_tuple(out_end, out_start, -1),
            ]
        else: add_black_arc(cur_pos, first_pos)

class GraphicalEnv:

    def __init__(self, tools):

        self.tools = tools

        # for visualisation
        #self.movable_objects = ()
        #self.visible_points_numer = ()
        #self.active_lines_numer, self.active_circles_numer = (), ()
        #self.extra_lines_numer, self.extra_circles_numer = (), ()
        #self.visible_arcs, self.visible_dists = (), ()
        #self.selectable_points = []
        #self.selectable_clines = []

        # long-term stored data
        self.steps = []
        self.gi_to_step = []
        self.gi_to_priority = []

        # numerical representation
        #self.num_points_d = dict()
        #self.num_lines_d = dict()
        #self.num_circles_d = dict()
        #self.num_points = ()
        #self.num_lines = ()
        #self.num_circles = ()

        # other internal links
        #self.li_to_gi_first = dict()
        #self.li_to_gi_last = dict()
        #self.li_to_num_data = dict()
        #self.line_to_points = defaultdict(list)
        #self.circle_to_points = defaultdict(list)
        #self.circle_to_arcs = defaultdict(list)
        #self.visible_points = set()
        #self.visible_lines = set()
        #self.visible_circles = set()

        self.refresh_steps()

    def li_root(self, li):
        return self.model.ufd.obj_to_root(li)
    def gi_to_li(self, gi): # graphical index to logic index
        li = self.step_env.local_to_global[gi]
        if li is None: return None
        return self.li_root(li)

    def li_to_num(self, li): # logic index to numerical object
        return self.model.num_model[li]

    def li_to_type(self, li): # logic index to type
        return self.model.obj_types[li]

    def gi_to_num(self, gi): # graphical index to numerical object
        li = self.step_env.local_to_global[gi]
        if li is None: return None
        return self.li_to_num(self.li_root(li))

    def gi_to_type(self, gi): # graphical index to numerical object
        li = self.step_env.local_to_global[gi]
        if li is None: return None
        return self.li_to_type(self.li_root(li))

    def select_obj(self, coor, scale, point_radius = 20, ps_radius = 20):
        try:
            d,p = min((
                (num.dist_from(coor), gi)
                for gi, num in self.selectable_points
            ), key = lambda x: x[0])
            if d * scale < point_radius: return p
        except ValueError:
            pass
        try:
            d,ps = min((
                (num.dist_from(coor), gi)
                for gi, num in self.selectable_clines
            ), key = lambda x: x[0])
            if d * scale < point_radius: return ps
        except ValueError:
            pass
        return None

    def update_movable_objects(self):
        self.movable_objects = []
        gi = 0
        for step in self.steps:
            if isinstance(step.tool, MovableTool):
                num = self.gi_to_num(gi)
                if num is not None:
                    self.movable_objects.append((gi, num))
            gi += len(step.tool.out_types)

    def select_movable_obj(self, coor, scale, radius = 20):
        if self.movable_objects:
            d,p = min(
                (num.dist_from(coor), gi)
                for gi, num in self.movable_objects
            )
            if d * scale < radius: return p
        return None

    def set_steps(self, steps):
        self.steps = steps
        self.gi_to_step = []
        for i,step in enumerate(steps):
            self.gi_to_step += [i]*len(step.tool.out_types)
        self.gi_to_priority = [2]*len(self.gi_to_step)
        self.refresh_steps()

    def add_step(self, step):
        try:
            self.step_env.run_steps((step,), 1)
            self.gi_to_step += [len(self.steps)]*len(step.tool.out_types)
            self.gi_to_priority += [2]*len(step.tool.out_types)
            self.steps.append(step)
            self.refresh_visible()
            self.update_movable_objects()
            return True
        except ToolError as e:
            if isinstance(e, ToolErrorException): raise e.e
            print("Tool failed: {}".format(e))
            self.refresh_steps()
            return False

    def pop_step(self):
        print("BACK")
        if not self.steps:
            print("No more steps to undo")
            return
        step = self.steps.pop()
        if len(step.tool.out_types) > 0:
            del self.gi_to_step[-len(step.tool.out_types):]
            del self.gi_to_priority[-len(step.tool.out_types):]
        self.refresh_steps()

    def refresh_steps(self):
        proof_checker.reset()
        self.model = LogicModel(basic_tools = self.tools)
        self.step_env = ToolStepEnv(self.model)
        self.step_env.run_steps(self.steps, 1, catch_errors = True)
        self.update_movable_objects()
        self.refresh_visible()

    def _get_num_obj(self, d, l, constructor, obj, keys):
        for key in keys:
            res = d.get(key, None)
            if res is not None: return res
        value = constructor(self, obj)
        l.append(value)
        for key in keys: d[key] = value
        return value

    def get_num_point(self, point):
        x0,y0 = map(int, np.floor(point.a / epsilon))
        keys = tuple(
            (x,y) for x in (x0,x0+1) for y in (y0,y0+1)
        )
        return self._get_num_obj(
            self.num_points_d, self.num_points,
            NumPointData, point, keys
        )
    def get_num_line(self, line):
        x0,y0,c0 = map(int, np.floor(line.data / epsilon))
        keys = tuple(
            (x*s,y*s,c*s)
            for x in (x0,x0+1) for y in (y0,y0+1)
            for c in (c0,c0+1) for s in (1, -1)
        )
        return self._get_num_obj(
            self.num_lines_d, self.num_lines,
            NumLineData, line, keys,
        )
    def get_num_circle(self, circle):
        x0,y0,r0 = map(int, np.floor(circle.data / epsilon))
        keys = tuple(
            (x,y,r)
            for x in (x0,x0+1) for y in (y0,y0+1)
            for r in (r0,r0+1)
        )
        return self._get_num_obj(
            self.num_circles_d, self.num_circles,
            NumCircleData, circle, keys,
        )
    def get_num_data(self, obj):
        if isinstance(obj, Point): return self.get_num_point(obj)
        elif isinstance(obj, Line): return self.get_num_line(obj)
        elif isinstance(obj, Circle): return self.get_num_circle(obj)
        else: raise Exception("Unexpected type {}".format(type(obj)))

    def update_rev_links(self):
        self.li_to_gi_first = dict()
        self.li_to_gi_last = dict()
        self.li_to_num_data = dict()
        self.num_points_d = dict()
        self.num_lines_d = dict()
        self.num_circles_d = dict()
        self.num_points = []
        self.num_lines = []
        self.num_circles = []

        for gi,li in enumerate(self.step_env.local_to_global):
            if li is None: continue
            if self.li_to_type(li) not in (Point, Line, Circle):
                continue
            li = self.li_root(li)
            self.li_to_gi_last[li] = gi
            gi_ori = self.li_to_gi_first.setdefault(li, gi)
            if gi is gi_ori:
                num = self.li_to_num(li)
                num_data = self.get_num_data(num)
                self.li_to_num_data[li] = num_data

        for li, gi in self.li_to_gi_last.items():
            num_data = self.li_to_num_data[li]
            priority = self.gi_to_priority[gi]
            num_data.add_active_candidate(li, (priority,gi))

    def select_visible_objs(self, objs):
        visible_objs = set()
        for num_data in objs:
            visible = num_data.select_visible()
            if visible is not None: visible_objs.add(visible)
        return visible_objs

    def select_visible_points(self):
        self.visible_points = self.select_visible_objs(self.num_points)
    def select_visible_lines(self):
        self.visible_lines = self.select_visible_objs(self.num_lines)
    def select_visible_circles(self):
        self.visible_circles = self.select_visible_objs(self.num_circles)

    def extract_knowledge(self):
        self.line_to_points = defaultdict(list)
        self.circle_to_points = defaultdict(list)
        self.circle_to_arcs = defaultdict(list)

        lies_on_labels = self.tools.lies_on_l, self.tools.lies_on_c
        dist_to_points = defaultdict(list)
        angle_to_data = defaultdict(list)
        for (label, args), out in self.model.ufd.data.items():
            if label is self.tools.lies_on_l:
                p,l = args
                if p in self.visible_points: self.line_to_points[l].append(p)
            elif label is self.tools.lies_on_c:
                p,c = args
                if p in self.visible_points: self.circle_to_points[c].append(p)
            elif label is self.tools.arc_length:
                p1,p2,c = args
                if p1 not in self.li_to_gi_first or p2 not in self.li_to_gi_first:
                    continue
                a, = out
                if self.model.angles.has_exact_difference(a, self.model.exact_angle):
                    continue
                angle_to_data[a].append((p1,p2,c))
            elif label is self.tools.dist:
                p1,p2 = args
                if p1 >= p2: continue
                if p1 not in self.li_to_gi_first or p2 not in self.li_to_gi_first:
                    continue
                d, = out
                dist_to_points[d].append((p1,p2))

        dist_num = 0
        for d, l in sorted(dist_to_points.items(), key = lambda x: x[0]):
            if len(l) <= 1: continue
            for a,b in l:
                if a not in self.visible_points or b not in self.visible_points:
                    continue
                na = self.li_to_num(a).a
                nb = self.li_to_num(b).a
                line = line_passing_np_points(na, nb)
                self.get_num_line(line).add_dist(
                    a,b, na,nb, dist_num
                )
            dist_num += 1

        angle_num = 0
        for a, l in sorted(angle_to_data.items(), key = lambda x: x[0]):
            if len(l) <= 1: continue
            for p1,p2,c in l:
                self.circle_to_arcs[c].append((p1,p2,angle_num))
            angle_num += 1

    def find_extra_clines(self):
        for line, points in self.line_to_points.items():
            if line in self.li_to_gi_first: continue
            if len(points) < 3: continue

            num_line = self.li_to_num(line)
            num_data = self.get_num_line(num_line)
            self.li_to_num_data[line] = num_data
            num_data.add_extra_candidate(line, len(points))

        circles = set(self.circle_to_points.keys()) | set(self.circle_to_arcs.keys())
        for circle in circles:
            if circle in self.li_to_gi_first: continue
            points_number = len(self.circle_to_points[circle])
            arcs_number = len(self.circle_to_arcs[circle])
            if arcs_number < 1 and points_number < 4: continue

            num_circle = self.li_to_num(circle)
            num_data = self.get_num_circle(num_circle)
            self.li_to_num_data[circle] = num_data
            num_data.add_extra_candidate(circle, (arcs_number, points_number))

    def distribute_dists(self):
        self.visible_dists = []
        for line_data in self.num_lines:
            line_data.distribute_dists()
    def distribute_arcs(self):
        self.visible_arcs = []
        for circle_data in self.num_circles:
            circle_data.distribute_arcs()

    def visible_export(self):
        self.visible_points_numer = [
            self.li_to_num(point)
            for point in self.visible_points
        ]
        self.active_lines_numer = []
        self.extra_lines_numer = []
        self.active_circles_numer = []
        self.extra_circles_numer = []
        self.selectable_clines = []

        for line_data in self.num_lines:
            if line_data.visible is None: continue
            exported = [
                line_data.line,
                line_data.colorization,
                [
                    self.li_to_num(point)
                    for point in self.line_to_points[line_data.visible]
                ]
            ]
            if line_data.is_active:
                self.active_lines_numer.append(exported)
                self.selectable_clines.append((
                    self.li_to_gi_first[line_data.visible],
                    line_data.line
                ))
            else: self.extra_lines_numer.append(exported)
        for circle_data in self.num_circles:
            if circle_data.visible is None: continue
            exported = [
                circle_data.circle,
                circle_data.colorization,
                [
                    self.li_to_num(point)
                    for point in self.circle_to_points[circle_data.visible]
                ]
            ]
            if circle_data.is_active:
                self.active_circles_numer.append(exported)
                self.selectable_clines.append((
                    self.li_to_gi_first[circle_data.visible],
                    circle_data.circle
                ))
            else: self.extra_circles_numer.append(exported)

        self.selectable_points = [
            (self.li_to_gi_first[li], self.li_to_num(li))
            for li in self.visible_points
        ]

    def refresh_visible(self):

        self.update_rev_links()
        self.select_visible_points()

        # lies_on, dist, arc_length
        # relevant to visible points / top_level objects
        # TODO: line angles, point_angles, exact_angles
        self.extract_knowledge()

        self.find_extra_clines()
        self.select_visible_lines()
        self.select_visible_circles()

        # TODO: find_visible_angles() # and arcs, possibly erase extra_line / circle
        # TODO: distribute_angles()

        self.distribute_dists()
        self.distribute_arcs()
        self.visible_export()

    def swap_priorities(self, gi, direction):
        li = self.gi_to_li(gi)
        candidates = self.li_to_num_data[li].active_candidates
        if len(candidates) <= 1:
            print("Unambiguous object")
            return

        candidates = sorted(
            ( cand for _, cand in candidates ),
            key = lambda cand: self.li_to_gi_last[cand],
        )
        #print(li, candidates)
        i = candidates.index(li)
        i2 = (i + direction) % len(candidates)
        #print("{} -> {}".format(i, i2))
        for li in candidates[i2+1:i+1]:
            self.gi_to_priority[self.li_to_gi_last[li]] = 1
        self.gi_to_priority[self.li_to_gi_last[candidates[i2]]] = 2
        #print([self.gi_to_priority[self.li_to_gi_last[x]] for x in candidates])

        self.refresh_visible()
