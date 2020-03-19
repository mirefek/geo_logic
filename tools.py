from fractions import Fraction
from sparse_row import SparseRow
from stop_watch import StopWatch

### Tool Exceptions
# used for tracing failed tools

class ToolError(Exception):
    def __init__(self, *args, **kwargs):
        self.tool_traceback = []
        Exception.__init__(self, *args, **kwargs)
    def __str__(self):
        msg = Exception.__str__(self)
        msg = "{}\n Tool Traceback:\n  ".format(msg)+"\n  ".join(
            "{}".format(line)
            for line in self.tool_traceback
        )
        return msg

class ToolErrorNum(ToolError):
    def __init__(self):
        ToolError.__init__(self, "Numerical check failed")
class ToolErrorLog(ToolError):
    def __init__(self):
        ToolError.__init__(self, "Fact not supported by logic")

class ToolErrorException(ToolError):
    def __init__(self, e):
        ToolError.__init__(self, "Python exception occured")
        self.e = e

### Tools

class Tool:
    def __init__(self, hyper_types, arg_types, out_types, name):
        self.hyper_types = hyper_types # types of hyperparameter, can be None
        self.arg_types = arg_types # geometrical types of arguments, can be None
        self.out_types = out_types # types of output
        self.name = name # string, can be none

    # if possible, add the tool to a dictionary of the form:
    # (name, input_types_or_none) -> tool
    def add_to_dict(self, d):
        if self.name is None: return
        if self.hyper_types is None or self.arg_types is None: in_types = None
        else: in_types = self.hyper_types+self.arg_types
        key = self.name, in_types
        assert(key not in d)
        d[key] = self

    def run(self, hyper_params, obj_args, logic, strictness):
        # strictness: 0 = postulate, 1 = check
        raise Exception("Not implemented")

class EqualObjects(Tool):
    def __init__(self, willingness = 0, name = "=="):
        self.willingness = willingness
        Tool.__init__(self, (), None, (), name)

    def run(self, hyper_params, obj_args, logic, strictness):
        assert(len(hyper_params) == 0)
        a,b = obj_args
        if not logic.num_model[a].identical_to(logic.num_model[b]):
            raise ToolErrorNum()
        elif strictness <= self.willingness: # postulate
            logic.glue(a,b)
            return ()
        else: # check
            if logic.check_equal(a,b): return ()
            else:
                print('not provably equal', a, b)
                raise ToolErrorLog()

class MemoizedTool(Tool):
    def __init__(self, arg_types, out_types, name):
        Tool.__init__(self, (), arg_types, out_types, name)
        self.symmetries = []
    def add_symmetry(self, perm): # for storing symmetrical inputs to the lookup table
        perm = tuple(perm)
        assert(set(perm) == set(range(len(perm)))) # check permutation
        assert(len(perm) == len(self.arg_types)) # check size
        # check preserved types
        perm_types = tuple(self.arg_types[i] for i in perm)
        assert(perm_types == self.arg_types)

        self.symmetries.append(perm)
        
    def memoize(self, args, logic, vals):
        logic.add_constr(self, args, vals)
        for perm in self.symmetries:
            perm_args = tuple(args[i] for i in perm)
            logic.add_constr(self, perm_args, vals)

    def run(self, hyper_params, obj_args, logic, strictness):

        memoized = logic.get_constr(self, obj_args)
        if memoized is not None: return memoized
        result = self.run_no_mem(obj_args, logic, strictness)
        self.memoize(obj_args, logic, result)

        return result

    def run_no_mem(self, args):
        raise Exception("Not implemented")

class PrimitivePred(MemoizedTool):
    def __init__(self, num_check, arg_types, name, willingness = 0):
        MemoizedTool.__init__(self, arg_types, (), name)
        # willingness: 0 = exact predicate, 1 = coexact
        self.willingness = willingness
        self.num_check = num_check

    def run_no_mem(self, args, logic, strictness):
        num_args = tuple(logic.num_model[arg] for arg in args)
        if not self.num_check(*num_args): raise ToolErrorNum()
        elif strictness > self.willingness: raise ToolErrorLog()
        else: return ()

class PrimitiveConstr(MemoizedTool):
    def __init__(self, num_eval, arg_types, out_types, name):
        MemoizedTool.__init__(self, arg_types, out_types, name)
        self.num_eval = num_eval

    def run_no_mem(self, args, logic, strictness):
        if strictness > 0:
            raise ToolError("Primitive construction cannot be run in check-mode")
        num_args = (logic.num_model[arg] for arg in args)
        num_outs = self.num_eval(*num_args)
        if len(self.out_types) == 1 and not isinstance(num_outs, (list, tuple)):
            num_outs = num_outs,
        assert(len(num_outs) == len(self.out_types))
        return logic.add_objs(num_outs)

# class for construction tools angle_compute and ratio_compute
class DimCompute(Tool):
    def __init__(self, obj_type, num_comp, postulate, name):
        Tool.__init__(self, None, None, (obj_type,), name)
        self.obj_type = obj_type # Angle / Ratio
        self.num_comp = num_comp # function for final construction
        self.postulate = postulate # function interacting with the logical core
    def run(self, hyper_params, args, logic, strictness):
        coefs = hyper_params[1:]
        assert(len(coefs) == len(args))

        frac_const = hyper_params[0]
        obj_sum = sum(logic.num_model[arg].data*float(coef)
                      for coef, arg in zip(coefs, args))
        new_obj_num = self.num_comp(obj_sum, frac_const)
        new_obj = logic.add_obj(self.obj_type(new_obj_num))

        equation = SparseRow(zip(args, coefs))
        equation[new_obj] = Fraction(-1)
        assert(all(isinstance(x, Fraction) for x in equation.values()))
        self.postulate(logic, equation, frac_const)

        return (new_obj,)

# class for predicate tools angle_pred and ratio_pred
class DimPred(Tool):
    def __init__(self, obj_type, num_check, postulate, check, name,
                 willingness = 0):
        self.obj_type = obj_type   # Angle / Ratio
        self.num_check = num_check
        self.postulate = postulate
        self.check = check
        self.willingness = willingness
        Tool.__init__(self, None, None, (), name)
    def run(self, hyper_params, args, logic, strictness):
        coefs = hyper_params[1:]
        assert(len(coefs) == len(args))
        frac_const = hyper_params[0]
        obj_sum = sum(logic.num_model[arg].data*float(coef)
                      for coef, arg in zip(coefs, args))
        if not self.num_check(obj_sum, frac_const):
            raise ToolErrorNum()

        equation = SparseRow(zip(args, coefs))

        if strictness <= self.willingness:
            self.postulate(logic, equation, frac_const)
            return ()
        elif self.check(logic, equation, frac_const):
            return ()
        else: raise ToolErrorLog()
