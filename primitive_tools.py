import geo_object
from geo_object import *
from tools import *
import primitive_constr
import primitive_pred
from itertools import product

"""
The main function here is "make_primitive_tool_dict" which
creates the initial dictionary of tools. The dictionary
is of the format
  (name, tool_name_or_none) -> tool,
and it is then used in parse.py for loading basic.gl
"""

### Functions for specific instances of DimCompute and DimPred

def angle_num_comp(obj_sum, frac_const):
    return (float(frac_const%1) + obj_sum)%1
def angle_num_check(obj_sum, frac_const):
    return eps_identical((float(frac_const%1) + obj_sum+0.5)%1, 0.5)
def angle_postulate(logic, *args): logic.add_angle_equation(*args)
def angle_check(logic, *args): return logic.check_angle_equation(*args)

def ratio_num_comp(obj_sum, frac_const):
    return np.array((np.log(float(frac_const)), 0),
                    dtype = float) + obj_sum
def ratio_num_check(obj_sum, frac_const):
    return eps_zero(np.array((np.log(float(frac_const)), 0),
                             dtype = float) + obj_sum)
def ratio_postulate(logic, *args): logic.add_ratio_equation(*args)
def ratio_check(logic, *args): return logic.check_ratio_equation(*args)

### A few more tools

class CustomRatio(Tool):
    def __init__(self):
        Tool.__init__(self, (float, float), (), (Ratio,), "custom_ratio")
    def run(self, hyper_params, obj_args, logic, strictness):
        return logic.add_obj(Ratio(hyper_params)),
class CustomAngle(Tool):
    def __init__(self):
        Tool.__init__(self, (float,), (), (Angle,), "custom_angle")
    def run(self, hyper_params, obj_args, logic, strictness):
        float_angle, = hyper_params
        return logic.add_obj(Angle(float_angle)),

"""
The following function is used for analyzing functions in
primitive_constr.py and primitive_pred.py. The input types
of such a function are anotated. They are mostly of the five
bacis types -- Point, Line, Circle, Angle, Ratio.
However, PointSet can be also there,
or an input that is not annotated at all in the case of "not_eq".
The function intypes_iter yields all the possible input types as
tuples of the five basic geometrical types.
"""
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
                continue  # exception, skip intersecting : L L ->
            if name == "lies_on": willingness = 0
            else: willingness = 1
            d[name, in_types] = PrimitivePred(f, in_types, name = name, willingness = willingness)

    # load constructions
    for fname, f in primitive_constr.__dict__.items():
        if not callable(f) or fname.startswith('_') or fname in geo_object.__dict__:
            continue
        out_type = f.__annotations__['return']
        for in_types in intypes_iter(f):
            out_types = (out_type,)
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
