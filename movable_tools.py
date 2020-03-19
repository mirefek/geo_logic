from geo_object import *
from tools import Tool, ToolErrorNum
from primitive_pred import not_collinear
from primitive_constr import circumcircle

def np_pair_is_rev(v1,v2):
    return v1[0]+np.e*v1[1] > v2[0]+np.e*v2[1]
def undirected_np_pair(v1, v2):
    if np_pair_is_rev(v1,v2): return v2,v1
    else: return v1,v2

"""
MovableTool = a tool which can be modified with the move tool in GUI.
  It includes the intersection
"""

class MovableTool(Tool):

    def __init__(self, hyper_types, arg_types, out_types, name, basic_tools):
        Tool.__init__(
            self, hyper_types, arg_types, out_types, name
        )
        self.basic_tools = basic_tools

    # helper function for postulating (used in add_corollaries of inherited objects)
    def add_lies_on(self, logic, p, cl):
        t = logic.obj_types[cl]
        if t == Line: self.basic_tools.lies_on_l.run((), (p, cl), logic, 0)
        elif t == Circle: self.basic_tools.lies_on_c.run((), (p, cl), logic, 0)
        else: raise Exception("Unexpected type {} of {}".format(type(cl), cl))

    # given a numerical repressentation and input objects (as numerical objects),
    # return the appropriate hyperparameters
    def get_hyperpar(self, p, *args):
        return self.new_hyperpar(None, p.a, *args)
    # the user catched an output object (last argument) at coor
    def get_grasp(self, coor, *args):
        return None
    # the user moved mouse after catching, what should be the hyperparameters now?
    def new_hyperpar(self, grasp, coor, *num_args):
        raise Exception("Not implemented")
    # given hyperparameters and input objects (as numerical objects), what is the 
    def num_eval(self, *args):
        raise Exception("Not implemented")
    # given input objects (as geometrical references) and the output object, postulate appropriate facts
    def add_corollaries(self, logic, *args):
        pass

    def run(self, hyper_params, obj_args, logic, strictness):
        num_args = tuple(logic.num_model[arg] for arg in obj_args)
        num_outs = self.num_eval(*(hyper_params+num_args))
        if len(self.out_types) == 1 and not isinstance(num_outs, (list, tuple)):
            num_outs = num_outs,
        assert(len(num_outs) == len(self.out_types))
        outs = logic.add_objs(num_outs)
        self.add_corollaries(logic, *(obj_args+outs))
        
        return outs

class FreePoint(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float, float), (), (Point,),
            "free_point", basic_tools,
        )

    def new_hyperpar(self, grasp, coor):
        return tuple(map(float, coor))
    def num_eval(self, x, y):
        return Point((x,y))

class PointOnCircle(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,), (Circle,), (Point,),
            "m_point_on", basic_tools,
        )

    def new_hyperpar(self, grasp, coor, c):
        if eps_identical(coor, c.c): return 0.,
        return vector_direction(coor-c.c),
    def num_eval(self, a, circ):
        return Point(circ.c + circ.r * vector_of_direction(a))
    def add_corollaries(self, logic, circ, p):
        self.add_lies_on(logic, p, circ)

class PointOnLine(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,float), (Line,), (Point,),
            "m_point_on", basic_tools
        )

    def new_hyperpar(self, grasp, coor, l):
        return tuple(map(float, coor))
    def num_eval(self, x, y, l):
        return Point(l.closest_on(np.array((x,y))))
    def add_corollaries(self, logic, line, p):
        self.add_lies_on(logic, p, line)

class Intersection(MovableTool):

    def __init__(self, arg_types, basic_tools,
                 get_candidates, order_candidates):
        MovableTool.__init__(
            self, (int,), arg_types, (Point,),
            "intersection", basic_tools,
        )
        self.get_candidates = get_candidates # intersection_lc / intersection_cc
        self.order_candidates = order_candidates # order_basic / order_by_point

    def ordered_candidates(self, num_args):
        candidates = self.get_candidates(*num_args[:2])
        if len(candidates) != 2: return None
        x1,x2 = candidates
        return self.order_candidates(x1, x2, *num_args)
    def new_hyperpar(self, grasp, coor, *num_args):
        candidates = self.ordered_candidates(num_args)
        if candidates is None: return 0,
        d1,d2 = (np.linalg.norm(x - coor) for x in candidates)
        return int(d2 < d1),
    def num_eval(self, i, *args):
        assert(i in (0,1))
        candidates = self.ordered_candidates(args)
        if candidates is None: raise ToolErrorNum()
        return Point(candidates[i])
    def add_corollaries(self, logic, cl1, cl2, *args):
        p = args[-1]
        self.add_lies_on(logic, p, cl1)
        self.add_lies_on(logic, p, cl2)

def order_basic(x1,x2, cl1,cl2):
    if isinstance(cl1, Circle) and isinstance(cl2, Circle):
        return x1,x2
    else: return undirected_np_pair(x1,x2)
def order_by_point(x1,x2, cl1,cl2, p):
    d1 = np.linalg.norm(x1-p.a)
    d2 = np.linalg.norm(x2-p.a)
    if eps_identical(d1,d2): return order_basic(x1,x2,cl1,cl2)
    elif d1 < d2: return x1,x2
    else: return x2,x1

class FreeLine(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,), (Point,), (Line,),
            "m_line", basic_tools
        )

    def get_hyperpar(self, l, p):
        return vector_direction(l.v),
    def new_hyperpar(self, grasp, coor, p):
        if eps_identical(p.a, coor): return 0.,
        else: return vector_direction(coor - p.a),
    def num_eval(self, d, p):
        n = vector_of_direction(d+0.5)
        return Line(n, np.dot(n, p.a))
    def add_corollaries(self, logic, p, l):
        self.add_lies_on(logic, p, l)

class FreeLineWithDir(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,float), (Angle,), (Line,),
            "m_line_with_dir", basic_tools
        )

    def get_hyperpar(self, l, p):
        return tuple(map(float, l.n*l.c))
    def new_hyperpar(self, grasp, coor, p):
        return tuple(map(float, coor))
    def num_eval(self, x,y, d):
        n = vector_of_direction(d.data+0.5)
        return Line(n, np.dot(n, np.array((x,y))))
    def add_corollaries(self, logic, d, l):
        d2, = self.basic_tools.direction_of.run((), (l,), logic, 1)
        logic.glue(d,d2)

class FreeCircleWithCenter(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,), (Point,), (Circle,),
            "m_circle_with_center", basic_tools
        )

    def get_hyperpar(self, c, p):
        return c.r,
    def new_hyperpar(self, grasp, coor, p):
        return max(0.001, np.linalg.norm(coor-p.a)),
    def num_eval(self, r, center):
        assert(r > 0)
        return Circle(center.a, r)
    def add_corollaries(self, logic, center, circ):
        center2, = self.basic_tools.center_of.run((), (circ,), logic, 1)
        logic.glue(center, center2)

class FreeCircleWithRadius(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,float), (Ratio,), (Circle,),
            "m_circle_with_radius", basic_tools
        )

    def get_hyperpar(self,  c, r):
        return tuple(map(float, c.c))
    def get_grasp(self, coor, r, c):
        return c.c - coor
    def new_hyperpar(self, grasp, coor, r):
        return tuple(map(float, coor+grasp))
    def num_eval(self, x, y, radius):
        return Circle(np.array((x,y)), np.exp(radius.x))
    def add_corollaries(self, logic, r, circ):
        r2, = self.basic_tools.radius_of.run((), (circ,), logic, 1)
        logic.glue(r, r2)

def get_circle_coef(circ, p1, p2):
    v = vector_perp_rot(p2.a-p1.a)
    return float(np.dot(v, (circ.c-p1.a)) / np.dot(v,v))
def center_from_coef(coef, p1, p2):
    v = vector_perp_rot(p2.a - p1.a)
    center = (p1.a+p2.a)/2 + v*coef
    return center

class CirclePassing1(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,float), (Point,), (Circle,),
            "m_circle_passing1", basic_tools
        )

    def get_hyperpar(self, c, p):
        return tuple(map(float, c.c - p.a))
    def get_grasp(self, coor, p, c):
        if eps_identical(p.a, coor): return 0
        coef = get_circle_coef(c, p, Point(coor))
        if abs(coef) <= 10: return coef
        else: return 0
    def new_hyperpar(self, grasp, coor, p):
        center = center_from_coef(grasp, p, Point(coor))
        return tuple(map(float, center-p.a))
    def num_eval(self, x,y, p):
        center = np.array((x,y))+p.a
        radius = np.linalg.norm(center-p.a)
        return Circle(center, radius)
    def add_corollaries(self, logic, p, circ):
        self.add_lies_on(logic, p, circ)

class CirclePassing2(MovableTool):

    def __init__(self, basic_tools):
        MovableTool.__init__(
            self, (float,), (Point,Point), (Circle,),
            "m_circle_passing2", basic_tools
        )

    def get_hyperpar(self, c, p1,p2):
        return get_circle_coef(c, p1, p2),
    def new_hyperpar(self, grasp, coor, p1,p2):
        max_coef = 100000.1
        p3 = Point(coor)
        if p3.identical_to(p1) or p3.identical_to(p2):
            return 0.,
        if not not_collinear(p1,p2,p3):
            return max_coef,
        coef = get_circle_coef(circumcircle(p1,p2,p3), p1,p2)
        if coef > max_coef: return max_coef,
        if coef < -max_coef: return -max_coef,
        return coef,

    def num_eval(self, coef, p1, p2):
        if p1.identical_to(p2): raise ToolErrorNum()
        center = center_from_coef(coef, p1, p2)
        radius = np.linalg.norm(p1.a-center)
        return Circle(center, radius)
    def add_corollaries(self, logic, p1, p2, circ):
        self.add_lies_on(logic, p1, circ)
        self.add_lies_on(logic, p2, circ)

"""
Movable tools are added by the following function after loading basic.gl.
The reason is that the movable tools
run certain postulates which sometimes requires tools defined there.
"""
def add_movable_tools(d, basic_tools):

    movables = [
        FreePoint, PointOnCircle, PointOnLine,
        FreeLine, FreeLineWithDir,
        FreeCircleWithCenter, FreeCircleWithRadius,
        CirclePassing1, CirclePassing2,
    ]
    for constructor in movables:
        tool = constructor(basic_tools)
        d[tool.name, tool.hyper_types+tool.arg_types] = tool
    for t1, get_cand in (Line, intersection_lc), (Circle, intersection_cc):
        for order, extra_arg in (order_basic, ()), (order_by_point, (Point,)):
            tool = Intersection((t1, Circle)+extra_arg, basic_tools, get_cand, order)
            d[tool.name, tool.hyper_types+tool.arg_types] = tool
