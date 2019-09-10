import numpy as np
from geo_object import *

class ConstrStep:
    def apply(self, obj_list):
        self.i_obj = [obj_list[i] for i in self.i_indices]
        if None in self.i_obj: obj = None
        else: obj = self.construct(*self.i_obj)
        if obj is not None: obj.index = len(obj_list)
        obj_list.append(obj)

class ConstrMovable(ConstrStep):
    pass

class ConstrPoint(ConstrMovable):
    def __init__(self, coor):
        self.coor = np.array(coor)
        self.i_indices = ()
    def construct(self):
        return Point(self.coor)

class ConstrDepPoint(ConstrMovable):
    def __init__(self, coor, ps):
        self.coor = np.array(coor)
        self.i_indices = (ps,)
    def construct(self, ps):
        true_coor = ps.closest_on(self.coor)
        return Point(true_coor)

class ConstrIntersectionFlex(ConstrMovable):
    def __init__(self, coor, ps1, ps2):
        self.coor = np.array(coor)
        self.i_indices = (ps1, ps2)
    def construct(self, ps1, ps2):
        intersections = [Point(x) for x in intersection(ps1, ps2)]
        if len(intersections) < 2: return None
        return min(intersections, key = lambda x: x.dist_from(self.coor))

class ConstrPointOnFixed(ConstrStep):
    def __init__(self, ps):
        self.coor = np.array((0,0))
        self.i_indices = (ps,)
    def construct(self, ps):
        true_coor = ps.closest_on(self.coor)
        return Point(true_coor)

class ConstrIntersectionUniq(ConstrStep):
    def __init__(self, l1, l2):
        self.i_indices = (l1, l2)
    def construct(self, l1, l2):
        intersections = [Point(x) for x in intersection(l1, l2)]
        if len(intersections) == 0: return None
        [p] = intersections
        return p
class ConstrIntersection0(ConstrStep):
    def __init__(self, ps1, ps2):
        self.i_indices = (ps1, ps2)
    def construct(self, ps1, ps2):
        intersections = [Point(x) for x in intersection(ps1, ps2)]
        if len(intersections) < 2: return None
        return intersections[0]
class ConstrIntersection1(ConstrStep):
    def __init__(self, ps1, ps2):
        self.i_indices = (ps1, ps2)
    def construct(self, ps1, ps2):
        intersections = [Point(x) for x in intersection(ps1, ps2)]
        if len(intersections) < 2: return None
        return intersections[1]
class ConstrIntersectionCloser(ConstrStep):
    def __init__(self, ps1, ps2, p):
        self.i_indices = (ps1, ps2, p)
    def construct(self, ps1, ps2, p):
        intersections = [Point(x) for x in intersection(ps1, ps2)]
        if len(intersections) < 2: return None
        return min(intersections, key = lambda x: x.dist_from(p.a))
class ConstrIntersectionRemoter(ConstrStep):
    def __init__(self, ps1, ps2, p):
        self.i_indices = (ps1, ps2, p)
    def construct(self, ps1, ps2, p):
        intersections = [Point(x) for x in intersection(ps1, ps2)]
        if len(intersections) < 2: return None
        return max(intersections, key = lambda x: x.dist_from(p.a))

class ConstrLine(ConstrStep):
    def __init__(self, p1, p2):
        self.i_indices = p1, p2
    def construct(self, p1, p2):
        if p1 == p2: return None
        return line_passing_points(p1, p2)

class ConstrCirc(ConstrStep):
    def __init__(self, p1, p2, c):
        self.i_indices = p1, p2, c
    def construct(self, p1, p2, c):
        if p1 == p2: return None
        r = np.linalg.norm(p1.a - p2.a)
        return Circle(c.a, r)

class ConstrCenter(ConstrStep):
    def __init__(self, c):
        self.i_indices = c,
    def construct(self, c):
        return Point(c.c)

class Construction:
    def __init__(self):
        self.steps = []
        self.obj_list = []
        self.step_dict = dict()
    def __len__(self):
        return len(self.steps)
    def truncate(self, new_len):
        assert(new_len >= 0 and new_len <= len(self))
        for step in self.steps[new_len:]:
            self.step_dict.pop((type(step), step.i_indices), None)
        self.steps = self.steps[:new_len]
        self.obj_list = self.obj_list[:new_len]
        print("{} objects".format(len(self)))

    def refresh(self):
        self.obj_list = []
        for step in self.steps: step.apply(self.obj_list)

    def add(self, constr, *args, force_add = False):
        deterministic = True
        args_i = []
        for arg in args:
            if isinstance(arg, GeoObject): args_i.append(arg.index)
            else:
                args_i.append(arg)
                deterministic = False
        args_i = tuple(args_i)
        reuse = deterministic and (constr, args_i) in self.step_dict
        if reuse:
            result = self.obj_list[self.step_dict[constr, args_i]]
        else:
            step = constr(*args_i)
            step.apply(self.obj_list)
            result = self.obj_list[-1]

        if result is None and not force_add:
            if not reuse: self.obj_list.pop()
            print("construction failed")
        else:
            if not reuse:
                if deterministic:
                    self.step_dict[constr, args_i] = len(self.steps)
                self.steps.append(step)
            print("{} objects".format(len(self.obj_list)))

        return result

    def pop(self):
        self.truncate(max(0, len(self-1)))
