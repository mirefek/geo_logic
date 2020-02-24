import geo_object
from geo_object import *
from tools import *
import primitive_constr
import primitive_pred
from itertools import product

def angle_num_comp(obj_sum, frac_const):
    return (float(frac_const%1) + obj_sum)%1
def angle_num_check(obj_sum, frac_const):
    return eps_identical((float(frac_const%1) + obj_sum+0.5)%1, 0.5)
def angle_postulate(model, *args): model.add_angle_equation(*args)
def angle_check(model, *args): return model.check_angle_equation(*args)

def ratio_num_comp(obj_sum, frac_const):
    return np.array((np.log(float(frac_const)), 0),
                    dtype = float) + obj_sum
def ratio_num_check(obj_sum, frac_const):
    return eps_zero(np.array((np.log(float(frac_const)), 0),
                             dtype = float) + obj_sum)
def ratio_postulate(model, *args): model.add_ratio_equation(*args)
def ratio_check(model, *args): return model.check_ratio_equation(*args)

class CustomRatio(Tool):
    def __init__(self):
        Tool.__init__(self, (float, float), (), (Ratio,), "custom_ratio")
    def run(self, meta_args, obj_args, model, strictness):
        return model.add_obj(Ratio(meta_args)),
class CustomAngle(Tool):
    def __init__(self):
        Tool.__init__(self, (float,), (), (Angle,), "custom_angle")
    def run(self, meta_args, obj_args, model, strictness):
        float_angle, = meta_args
        return model.add_obj(Angle(float_angle)),

def intypes_iter(f):
    in_varnames = f.__code__.co_varnames[:f.__code__.co_argcount]
    in_types = [f.__annotations__.get(name, None) for name in in_varnames]
    in_types_tups = [
        (Line, Circle) if t == PointSet else (t,)
        for t in in_types
    ]
    for in_types in product(*in_types_tups):
        if None not in in_types: yield in_types
        else:
            for joker_t in (Point, Line, Circle, Angle, Ratio):
                yield tuple(joker_t if t is None else t for t in in_types)

def make_primitive_tool_dict():
    d = dict()

    # load predicates
    for name, f in primitive_pred.__dict__.items():
        if not callable(f) or name.startswith('_') or name in geo_object.__dict__:
            continue
        for in_types in intypes_iter(f):
            if name == "intersecting" and in_types[:2] == (Line, Line):
                continue
            if name == "lies_on": willingness = 0
            else: willingness = 1
            d[name, in_types] = PrimitivePred(f, in_types, name = name, willingness = willingness)

    # load constructions and movable tools
    for fname, f in primitive_constr.__dict__.items():
        if not callable(f) or fname.startswith('_') or fname in geo_object.__dict__:
            continue
        out_type = f.__annotations__['return']
        for in_types in intypes_iter(f):
            if fname in ("intersection_remoter", "intersection0") and in_types[:2] == (Line, Line):
                continue
            out_types = (out_type,)
            #if in_types[:2] == (float, float):
            #    name = fname
            #    tool = MovableTool(f, in_types[2:], out_types, name = name)
            #    if fname == "point_on":
            #        tool.add_effect(d["lies_on", out_types+in_types[2:]])
            #        pass
            #else:
            name = "prim__"+fname
            tool = PrimitiveConstr(f, in_types, out_types, name = name)

            d[name, in_types] = tool

    # dimension tools
    dim_tools = [
        DimCompute(Angle, angle_num_comp, angle_postulate, "angle_compute"),
        DimCompute(Ratio, ratio_num_comp, ratio_postulate, "ratio_compute"),
        DimPred(Angle, angle_num_check, angle_postulate, angle_check, "angle_pred"),
        DimPred(Ratio, ratio_num_check, ratio_postulate, ratio_check, "ratio_pred"),
        CustomRatio(),
        CustomAngle(),
    ]
    for tool in dim_tools: tool.add_to_dict(d)

    # equality tool
    eq_tool = EqualObjects()
    for t in (Point, Line, Circle, Angle, Ratio):
        d[eq_tool.name, (t,t)] = eq_tool

    return d

if __name__ == "__main__":
    d = make_primitive_tool_dict()
    for key, value in d.items():
        if isinstance(key, tuple):
            name, in_types = key
            in_types = ' '.join(x.__name__ for x in in_types)
        else:
            name, in_types = key, "???"
        out_types = ' '.join(x.__name__ for x in value.out_types)
        if out_types == '': out_types = '()'
        print("{} : {} -> {}".format(name, in_types, out_types))
