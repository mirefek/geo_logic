from tool_step import ToolStepEnv, proof_checker
from logic_model import LogicModel
import geo_object
from geo_object import *
import itertools
from collections import defaultdict
from tools import ToolError, ToolErrorException
from movable_tools import MovableTool

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
        self.angles_ppl = []
        self.angles_ll = []
        self.exact_lines = defaultdict(set)
        self.exact_angles = defaultdict(list)

    def add_active_candidate(self, li, priority):
        self.active_candidates.append((priority, li))
    def select_visible(self):
        if self.active_candidates:
            _,self.visible = max(self.active_candidates)
        return self.visible
    def add_angle(self, angle_data):
        if angle_data.color < 0:
            d, = self.env.model.get_constr(self.env.tools.direction_of, (angle_data.l1,))
            d,_ = self.env.model.angles.equal_to[d]
            self.exact_lines[d].update((angle_data.l1, angle_data.l2))
            self.exact_angles[d].append(angle_data)
        elif isinstance(angle_data, AnglePPLData):
            self.angles_ppl.append(angle_data)
        else:
            self.angles_ll.append(angle_data)
    def add_exact(self, line, d):
        self.exact_lines[d].add(line)

    def distribute_angles(self):
        if not self.angles_ppl and not self.angles_ll: return
        used = set()
        segments = []
        for angle in self.angles_ppl:
            angle.find_l1_dir()

            key = (angle.l1, angle.l2, angle.l1_dir_sgn)
            if key in used: continue
            used.add(key)

            angle.find_arc()
            segments.append((angle.pos_a, angle.pos_b, 0, angle))
        for angle in self.angles_ll:
            if (angle.l1, angle.l2, 1) in used or (angle.l1, angle.l2, -1) in used:
                continue
            angle.find_l1_dir()
            used.add((angle.l1, angle.l2, angle.l1_dir_sgn))
            
            angle.find_arc()
            segments.append((angle.pos_a, angle.pos_b, 0, angle))

        ang_lev = distribute_segments_cyc(segments)
        self.env.visible_angles.extend(
            (ang.p.a, ang.pos_a, ang.pos_b, ang.color, lev)
            for ang,lev in ang_lev
        )

    def distribute_exact_angles(self):
        for d, lines in self.exact_lines.items():
            lines &= self.env.visible_lines
            if len(lines) < 1: continue
            line_pos = sorted(
                (vector_direction(self.env.li_to_num(l).v)%1, l)
                for l in lines
            )
            li_to_pos_index = dict(
                (li,i) for i,(pos,li) in enumerate(line_pos)
            )
            half_circ = len(line_pos)
            line_pos = [
                pos for (pos, l) in line_pos
            ] + [
                pos+1 for (pos, l) in line_pos
            ]
            full_circ = len(line_pos)
            used = [False]*full_circ

            def set_used(i1, i2):
                i2 = i1 + (i2-i1) % half_circ
                for i in range(i1, i2):
                    used[i % full_circ] = True
            def count_used(i1, i2):
                i2 = i1 + (i2-i1) % half_circ
                res = 0
                for i in range(i1, i2):
                    if used[i % full_circ]: res += 1
                return res
            def get_start_from_angle(angle):
                pos_real = vector_direction(angle.l1_num.v * angle.l1_dir_sgn)
                i = li_to_pos_index[angle.l1]
                if eps_identical((line_pos[i] - pos_real + 1)%2, 1): return i
                else: return i+half_circ

            ambig_angles = []
            for angle in self.exact_angles[d]:
                if isinstance(angle, AnglePPLData):
                    angle.find_l1_dir()
                    i1 = get_start_from_angle(angle)
                    i2 = li_to_pos_index[angle.l2]
                    set_used(i1,i2)
                else: ambig_angles.append(angle)
            for angle in ambig_angles:
                i1 = li_to_pos_index[angle.l1]
                i2 = li_to_pos_index[angle.l2]
                count1 = count_used(i1, i2)
                count2 = count_used(i1+half_circ, i2)
                if count1 > count2: set_used(i1, i2)
                elif count2 > count1: set_used(i1+half_circ, i2)
                else:
                    angle.find_l1_dir()
                    i1 = get_start_from_angle(angle)
                    set_used(i1,i2)
            last_added = None
            for i in range(half_circ):
                if not used[i] and not used[i+half_circ]:
                    used[i] = True
                    last_added = i
            if last_added is not None: used[last_added] = False
            for i,i_used in enumerate(used):
                if not i_used: continue
                pos1 = line_pos[i]
                pos2 = line_pos[(i+1)%full_circ]
                self.env.visible_exact_angles.append((self.point.a, pos1, pos2))

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

        self.colorization = []
        def add_black_arc(pos_a, pos_b):
            if eps_identical(pos_a, pos_b): return
            #print("ADD_BLACK", pos_a, pos_b)
            #print("OUTSIDE", out_start, out_end)
            if out_start is not None and eps_bigger((pos_b-pos_a)%2, 1):
                #print("  outside")
                if not eps_identical(pos_a, out_start): self.colorization.append((pos_a, out_start, -1))
                self.colorization.append((out_start, out_end, -2))
                if not eps_identical(out_end, pos_b): self.colorization.append((out_end, pos_b, -1))
            else:
                #print("  inside")
                self.colorization.append((pos_a, pos_b, circ_color))

        cur_pos = None
        for (pos_a, pos_b, col), lev in arc_lev:
            if lev == 0:
                if cur_pos is not None:
                    add_black_arc(cur_pos, pos_a)
                else: first_pos = pos_a
                cur_pos = pos_b
                self.colorization.append((pos_a, pos_b, col))
            else: self.env.visible_arcs.append(
                    (pos_a, pos_b, self.circle, col, lev)
            )

        if cur_pos is None:
            if out_start is None: self.colorization = None
            else: self.colorization = [
                (out_start, out_end, -2),
                (out_end, out_start, -1),
            ]
        else: add_black_arc(cur_pos, first_pos)

class ArcData:
    def __init__(self, env,p1,p2,c):
        self.env = env
        self.p1 = p1
        self.p2 = p2
        self.c = c
    def activate(self, color):
        self.env.circle_to_arcs[self.c].append((self.p1,self.p2,color))

class AngleLLData:
    def __init__(self, env,l1,l2):
        self.env = env
        self.l1 = l1
        self.l2 = l2
    def activate(self, color):
        self.color = color
        self.env.angles_ll.append(self)
        self.env.line_to_angle_number[self.l1] += 1
        self.env.line_to_angle_number[self.l2] += 1
    def add_to_point(self):
        self.p = Point(intersection_ll(
            self.env.li_to_num(self.l1),
            self.env.li_to_num(self.l2),
        ))
        self.l1_num = self.env.li_to_num_data[self.l1].line
        self.l2_num = self.env.li_to_num_data[self.l2].line
        self.env.get_num_point(self.p).add_angle(self)
    def find_l1_dir(self):
        points = self.env.line_to_points[self.l1]
        if not points:
            self.l1_dir_sgn = 1
            return
        positions = [
            np.dot(self.env.li_to_num(p).a, self.l1_num.v)
            for p in points
        ]
        min_pos = min(positions)
        max_pos = max(positions)
        pos = np.dot(self.p.a, self.l1_num.v)
        if eps_bigger(pos - min_pos, max_pos - pos): self.l1_dir_sgn = -1
        else: self.l1_dir_sgn = 1
    def find_arc(self):
        self.pos_a = vector_direction(self.l1_num.v * self.l1_dir_sgn)%2
        self.pos_b = vector_direction(self.l2_num.v)%2
        if (self.pos_b - self.pos_a)%2 > 1:
            if self.pos_b >= 1: self.pos_b -= 1
            else: self.pos_b += 1
        if self.pos_b < self.pos_a: self.pos_b += 2

class AnglePPLData(AngleLLData):
    def __init__(self, env,p1,p2,l2):
        self.p1 = p1
        self.p2 = p2
        l1, = env.model.get_constr(env.tools.line, (p1, p2))
        AngleLLData.__init__(self, env, l1, l2)
    def find_l1_dir(self):
        if np.dot(self.env.li_to_num(self.p2).a - self.env.li_to_num(self.p1).a, self.l1_num.v) > 0:
            self.l1_dir_sgn = 1
        else: self.l1_dir_sgn = -1        

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
        #self.selectable_lines = []
        #self.selectable_circles = []

        # long-term stored data
        self.steps = []
        self.gi_to_step_i = []
        self.gi_to_priority = []
        self.gi_to_hidden = []

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

        self.hl_proposals = ()
        self.hl_helpers = ()
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

    def update_movable_objects(self):
        self.movable_points = []
        self.movable_clines = []
        gi = 0
        for step in self.steps:
            if isinstance(step.tool, MovableTool):
                num = self.gi_to_num(gi)
                if num is not None:
                    if isinstance(num, Point):
                        self.movable_points.append((gi, num))
                    else: self.movable_clines.append((gi, num))
            gi += len(step.tool.out_types)

    def select_movable_obj(self, coor, scale, radius = 20):
        if self.movable_points:
            d,p = min(
                (num.dist_from(coor), gi)
                for gi, num in self.movable_points
            )
            if d * scale < radius: return p
        if self.movable_clines:
            d,p = min(
                (num.dist_from(coor), gi)
                for gi, num in self.movable_clines
            )
            if d * scale < radius: return p
        return None

    def gi_to_step(self, gi):
        i = self.gi_to_step_i[gi]
        return self.steps[i]

    def set_steps(self, steps):
        self.steps = steps
        self.gi_to_step_i = []
        for i,step in enumerate(steps):
            self.gi_to_step_i += [i]*len(step.tool.out_types)
        self.gi_to_priority = [2]*len(self.gi_to_step_i)
        self.gi_to_hidden = [False]*len(self.gi_to_step_i)
        self.refresh_steps(False)

    def add_step(self, step, update = True):
        try:
            ori_len = len(self.step_env.local_to_global)
            self.step_env.run_steps((step,), 1)
            new_len = len(self.step_env.local_to_global)
            self.gi_to_step_i += [len(self.steps)]*len(step.tool.out_types)
            self.gi_to_priority += [2]*len(step.tool.out_types)
            self.gi_to_hidden += [False]*len(step.tool.out_types)
            self.steps.append(step)
            if update:
                self.refresh_visible()
                self.update_movable_objects()
            return tuple(range(ori_len, new_len))
        except ToolError as e:
            if isinstance(e, ToolErrorException): raise e.e
            print("Tool failed: {}".format(e))
            self.refresh_steps()
            return None

    def pop_step(self):
        print("BACK")
        if not self.steps:
            print("No more steps to undo")
            return
        step = self.steps.pop()
        if len(step.tool.out_types) > 0:
            del self.gi_to_step_i[-len(step.tool.out_types):]
            del self.gi_to_priority[-len(step.tool.out_types):]
            del self.gi_to_hidden[-len(step.tool.out_types):]
        self.refresh_steps()

    def refresh_steps(self, catch_errors = True):
        proof_checker.reset()
        self.model = LogicModel(basic_tools = self.tools)
        self.step_env = ToolStepEnv(self.model)
        self.step_env.run_steps(self.steps, 1, catch_errors = catch_errors)
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
            if self.gi_to_hidden[gi]: continue
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
        self.angles_ll = []
        direction_to_line = defaultdict(list)
        direction_q_to_line = defaultdict(list)
        self.line_to_angle_number = defaultdict(int)
        self.visible_parallels = []

        lies_on_labels = self.tools.lies_on_l, self.tools.lies_on_c
        dist_to_points = defaultdict(list)
        angle_to_data = defaultdict(list)
        for (label, args), out in self.model.ufd.data.items():
            if label is self.tools.lies_on_l:      #### lies_on
                p,l = args
                if p in self.li_to_gi_first: self.line_to_points[l].append(p)
            elif label is self.tools.lies_on_c:
                p,c = args
                if p in self.li_to_gi_first: self.circle_to_points[c].append(p)
            elif label is self.tools.arc_length:   #### arc length
                p1,p2,c = args
                if p1 not in self.li_to_gi_first or p2 not in self.li_to_gi_first:
                    continue
                a, = out
                if self.model.angles.has_exact_difference(a, self.model.exact_angle):
                    continue
                angle_to_data[a].append(ArcData(self, p1,p2,c))
            elif label is self.tools.dist:         #### distance
                p1,p2 = args
                if p1 >= p2: continue
                if p1 not in self.li_to_gi_first or p2 not in self.li_to_gi_first:
                    continue
                d, = out
                dist_to_points[d].append((p1,p2))
            elif label is self.tools.direction_of: #### exact angles
                l, = args
                if l not in self.li_to_gi_first: continue
                d, = out
                direction_to_line[d].append(l)
                direction_q_to_line[self.model.angles.equal_to[d][0]].append((l,d))

        #### angles
        zero_angle = Angle(0)
        for (label, args), out in self.model.ufd.data.items():
            if label is self.tools.angle_ll:
                l1,l2 = args
                if l1 not in self.li_to_gi_first and len(self.line_to_points[l1]) < 2:
                    continue
                if l2 not in self.li_to_gi_first and len(self.line_to_points[l2]) < 2:
                    continue
                a, = out
                num = self.li_to_num(a)
                if num.identical_to(zero_angle): continue
                angle_to_data[a].append(AngleLLData(self, l1,l2))
            elif label is self.tools.angle_ppl:
                p1,p2,l = args
                if p1 not in self.li_to_gi_first or p2 not in self.li_to_gi_first:
                    continue
                if len(self.line_to_points[l]) < 2: continue
                a, = out
                num = self.li_to_num(a)
                if num.identical_to(zero_angle): continue
                angle_to_data[a].append(AnglePPLData(self, p1,p2,l))

        #### Filter out hidden points
        for line, points in self.line_to_points.items():
            points = [p for p in points if p in self.visible_points]
            self.line_to_points[line] = points
        for circle, points in self.line_to_points.items():
            points = [p for p in points if p in self.visible_points]
            self.circle_to_points[circle] = points

        #### store repeated dists
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

        #### store repeated angles / arcs
        angle_num = 0
        for a, l in sorted(angle_to_data.items(), key = lambda x: x[0]):
            if self.model.angles.has_exact_difference(a, self.model.exact_angle):
                for data in l: data.activate(-1)
            else:
                if len(l) <= 1: continue
                for data in l: data.activate(angle_num)
                angle_num += 1

        #### store additional exact angles
        for d,lines in direction_q_to_line.items():
            for (l1,d1),(l2,d2) in itertools.combinations(lines, 2):
                if d1 == d2: continue
                p = Point(intersection_ll(
                    self.li_to_num(l1),
                    self.li_to_num(l2))
                )
                point_data = self.get_num_point(p)
                point_data.add_exact(l1,d)
                point_data.add_exact(l2,d)

        #### store parallels
        parallel_num = 0
        for d,lines in sorted(direction_to_line.items(), key = lambda x: x[0]):
            if len(lines) < 2: continue
            for l in lines:
                self.visible_parallels.append((self.li_to_num(l), parallel_num))
            parallel_num += 1

    def find_extra_clines(self):
        lines = set(self.line_to_points.keys()) | set(self.line_to_angle_number.keys())
        for line in lines:
            if line in self.li_to_gi_first: continue
            points_number = len(self.line_to_points[line])
            angle_number = self.line_to_angle_number[line]
            if points_number < 3 and not angle_number: continue
            if points_number < 2: continue

            num_line = self.li_to_num(line)
            num_data = self.get_num_line(num_line)
            self.li_to_num_data[line] = num_data
            num_data.add_extra_candidate(line, (angle_number, points_number))

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

    def li_is_visible(self, li):
        num_data = self.li_to_num_data.get(li, None)
        if num_data is None or num_data.visible is None: return False
        return num_data.visible == li
    def filter_visible_angles(self):
        angles_ll_ori = self.angles_ll
        self.angles_ll = []
        self.line_to_angle_number = defaultdict(int)
        for a in angles_ll_ori:
            if a.l1 in self.visible_lines and a.l2 in self.visible_lines:
                a.activate(a.color)
                a.add_to_point()

        # remove redundant lines
        for line_data in self.num_lines:
            if line_data.visible is None or line_data.is_active: continue
            li = line_data.visible
            if len(self.line_to_points[li]) < 3 and li not in self.line_to_angle_number:
                continue

    def distribute_dists(self):
        self.visible_dists = []
        for line_data in self.num_lines:
            line_data.distribute_dists()
    def distribute_arcs(self):
        self.visible_arcs = []
        for circle_data in self.num_circles:
            circle_data.distribute_arcs()
    def distribute_angles(self):
        self.visible_angles = []
        self.visible_exact_angles = []
        for point_data in self.num_points:
            point_data.distribute_angles()
            point_data.distribute_exact_angles()

    def update_hl(self, proposals, selected, helpers):
        self.hl_proposals = proposals
        self.hl_helpers = helpers
        self.obj_is_selected = dict()
        for obj in selected:
            if isinstance(obj, tuple):
                data = obj[1:]
                obj = obj[0]
            else: data = True
            if obj >= len(self.step_env.local_to_global): continue
            li = self.gi_to_li(obj)
            if li is None: continue
            self.obj_is_selected[li] = data
        self.visible_export()

    def visible_export(self):
        self.visible_points_numer = [
            (self.li_to_num(point),
             self.obj_is_selected.get(point, None))
            for point in self.visible_points
        ]
        self.active_lines_numer = []
        self.extra_lines_numer = []
        self.active_circles_numer = []
        self.extra_circles_numer = []
        self.selectable_lines = []
        self.selectable_circles = []

        for line_data in self.num_lines:
            if line_data.visible is None: continue
            exported = [
                line_data.line,
                line_data.colorization,
                [
                    self.li_to_num(point)
                    for point in self.line_to_points[line_data.visible]
                ],
                self.obj_is_selected.get(line_data.visible, None),
            ]
            if line_data.is_active:
                self.active_lines_numer.append(exported)
                self.selectable_lines.append((
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
                ],
                self.obj_is_selected.get(circle_data.visible, None),
            ]
            if circle_data.is_active:
                self.active_circles_numer.append(exported)
                self.selectable_circles.append((
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
        self.extract_knowledge()

        self.find_extra_clines()
        self.select_visible_lines()
        self.select_visible_circles()
        self.filter_visible_angles()

        self.distribute_dists()
        self.distribute_arcs()
        self.distribute_angles()

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

    def hide(self, gi):
        li = self.gi_to_li(gi)
        gi_first = self.li_to_gi_first[li]
        gi_last = self.li_to_gi_last[li]
        print("hide li {} in range {} -- {}".format(li, gi_first, gi_last))
        for gi in range(gi_first, gi_last+1):
            if self.gi_to_li(gi) == li:
                print("  hide gi {}".format(gi))
                self.gi_to_hidden[gi] = True
        self.refresh_visible()
