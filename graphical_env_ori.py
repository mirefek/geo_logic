from tool_step import ToolStepEnv, proof_checker
from logic_model import LogicModel
import geo_object
from geo_object import *
import itertools
from collections import defaultdict
from tools import ToolError, ToolErrorException, MovableTool

def find_duplicities(objs, epsilon = geo_object.epsilon):
    glued_to = dict()
    d = dict()
    def add_to_dict(ident, t, data):
        idata = np.floor(data / epsilon).astype(int)
        for offset in itertools.product(*((0,1) for _ in idata)):
            d_index = idata + np.array(offset, dtype = int)
            d_index = tuple(d_index)
            ident2 = d.setdefault((t, d_index), ident)
            if ident != ident2:
                glued_to[ident].append(ident2)
                glued_to[ident2].append(ident)

    ident_list = list()
    for identifier, obj in objs:
        t = type(obj)
        ident_list.append(identifier)
        glued_to.setdefault(identifier, list())
        add_to_dict(identifier, t, obj.data)
        if t == Line: add_to_dict(identifier, t, -obj.data)

    for identifier in ident_list:
        if identifier not in glued_to: continue
        component = list()
        def find_component(x):
            x_objs = glued_to.pop(x, None)
            if x_objs is None: return
            component.append(x)
            for x2 in x_objs:
                find_component(x2)
        find_component(identifier)
        if component: yield component

def distribute_segments(segments):
    segments.sort(key = lambda x: (x[0], -x[1]))
    occupied = []
    for a,b,start,info in segments:
        for lev,b_ori in enumerate(occupied):
            if lev < start: continue
            if not eps_smaller(a, b_ori):
                occupied[lev] = b
                break
        else:
            lev = len(occupied)
            occupied.append(b)
        yield info,lev

# (a,b,info), a in (0,1), b in (0,2), cyc mod 1
def distribute_segments_cyc(segments):
    segments.sort(key = lambda x: (x[0], -x[1]))
    occupied = []
    for a,b,start,info in segments:
        for lev,(a_ori,b_ori) in enumerate(occupied):
            if lev < start: continue
            if not eps_smaller(a, b_ori) and not eps_smaller(a_ori, b-1):
                occupied[lev] = a_ori,b
                break
        else:
            lev = len(occupied)
            occupied.append((a,b))
        yield info,lev

class GraphicalEnv:
    def __init__(self, tools):
        self.steps = []
        self.gi_to_step = []
        self.gi_to_priority = []
        self.tools = tools
        self.refresh_steps()

    def refresh_steps(self):
        proof_checker.reset()
        self.model = LogicModel(basic_tools = self.tools)
        self.step_env = ToolStepEnv(self.model)
        self.step_env.run_steps(self.steps, 1, catch_errors = True)
        self.refresh_visible()

    def refresh_visible(self):
        used = set()
        max_i = len(self.step_env.local_to_global)-1
        visible_candidates = []
        for rev_i, li in enumerate(reversed(self.step_env.local_to_global)):
            gi = max_i - rev_i
            if li is None: continue
            li = self.model.ufd.obj_to_root(li)
            num = self.li_to_num(li)
            if not issubclass(self.model.obj_types[li], (Point, PointSet)): continue
            if li in used: continue
            used.add(li)
            visible_candidates.append((gi, num))
        self.num_glued = tuple(find_duplicities(visible_candidates))

        self.visible_points = []
        self.visible_clines = []
        visible_points_li = set()
        visible_lines_li = set()
        visible_circles_li = set()
        visible_clines_li = set()

        for group in self.num_glued:
            group.sort()
            gi = max(group, key = lambda gi: (self.gi_to_priority[gi], gi))
            li = self.gi_to_li(gi)
            num = self.li_to_num(li)
            if isinstance(num, Point):
                self.visible_points.append((gi, num))
                visible_points_li.add(li)
            else:
                self.visible_clines.append((gi, num))
                t = self.li_to_type(li)
                if t == Line: visible_lines_li.add(li)
                elif t == Circle: visible_circles_li.add(li)
                else: raise Exception("unexpected type: {}", t)
                visible_clines_li.add(li)

        lies_on_labels = self.tools.lies_on_l, self.tools.lies_on_c
        dist_label = self.tools.dist
        dist_to_points = defaultdict(list)
        self.lies_on_data = []
        for (label, args), out in self.model.ufd.data.items():
            if label in lies_on_labels:
                p,ps = args
                if p in visible_points_li and ps in visible_clines_li:
                    self.lies_on_data.append(args)
            elif label is dist_label:
                a,b = args
                if a >= b: continue
                if a not in visible_points_li or b not in visible_points_li:
                    continue
                d, = out
                dist_to_points[d].append((a,b))

        dist_col_data = []
        self.dist_color_num = 0
        for d, l in sorted(dist_to_points.items(), key = lambda x: x[0]):
            if len(l) <= 1: continue
            col = self.dist_color_num
            self.dist_color_num += 1
            dist_col_data.extend(
                (self.li_to_num(a).a, self.li_to_num(b).a ,col)
                for (a,b) in l
            )

        lines = [
            (i, line_passing_np_points(a,b))
            for i,(a,b,_) in enumerate(dist_col_data)
        ]
        lines.extend(
            (-1-li, self.li_to_num(li))
            for li in visible_lines_li
        )
        line_groups = tuple(find_duplicities(lines))

        self.dist_col_lev = []
        for group in line_groups:
            dist_indices = [i for i in group if i >= 0]
            if len(dist_indices) == 0: continue
            offset = int(len(dist_indices) < len(group))
            dir_vec = lines[dist_indices[0]][1].v
            segments = []
            for i in dist_indices:
                a,b,col = dist_col_data[i]
                pos_a = np.dot(dir_vec, a)
                pos_b = np.dot(dir_vec, b)
                if pos_b < pos_a:
                    a,b = b,a
                    pos_a, pos_b = pos_b, pos_a
                segments.append((pos_a,pos_b,0,(a,b,col)))
            self.dist_col_lev.extend(
                (a,b,col,lev+offset)
                for (a,b,col),lev in distribute_segments(segments)
            )

    def swap_priorities(self, gi, direction):
        for group in self.num_glued:
            if gi in group: break
        else: raise Exception("swap_priorities: object {} not found".format(gi))

        i = group.index(gi)
        if len(group) == 1:
            print("Unambiguous object")
            return

        i2 = (i + direction) % len(group)
        for obj in group[i2+1:i+1]:
            self.gi_to_priority[obj] = 1
        self.gi_to_priority[group[i2]] = 2

        print("{} -> {}".format(i, i2))
        print([(x, self.gi_to_priority[x]) for x in group])
        self.refresh_visible()

    def gi_to_li(self, gi): # graphical index to logic index
        li = self.step_env.local_to_global[gi]
        if li is None: return None
        return self.model.ufd.obj_to_root(li)

    def li_to_num(self, li): # logic index to numerical object
        return self.model.num_model[li]

    def li_to_type(self, li): # logic index to type
        return self.model.obj_types[li]

    def gi_to_num(self, gi): # graphical index to numerical object
        li = self.step_env.local_to_global[gi]
        if li is None: return None
        return self.li_to_num(self.model.ufd.obj_to_root(li))

    def gi_to_type(self, gi): # graphical index to numerical object
        li = self.step_env.local_to_global[gi]
        if li is None: return None
        return self.li_to_type(self.model.ufd.obj_to_root(li))

    def select_obj(self, coor, scale, point_radius = 20, ps_radius = 20):
        try:
            d,p = min((
                (num.dist_from(coor), gi)
                for gi, num in self.visible_points
            ), key = lambda x: x[0])
            if d * scale < point_radius: return p
        except ValueError:
            pass
        try:
            d,ps = min((
                (num.dist_from(coor), gi)
                for gi, num in self.visible_clines
            ), key = lambda x: x[0])
            if d * scale < point_radius: return ps
        except ValueError:
            pass
        return None

    def select_movable_obj(self, coor, scale, radius = 20):
        movables = []
        gi = 0
        for step in self.steps:
            if isinstance(step.tool, MovableTool):
                num = self.gi_to_num(gi)
                if num is not None:
                    movables.append((num.dist_from(coor), gi))
            gi += len(step.tool.out_types)
        if movables:
            d,p = min(movables)
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

