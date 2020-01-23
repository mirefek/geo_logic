from fractions import Fraction
from sparse_elim import SparseRow

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

class Tool:
    def __init__(self, meta_types, arg_types, out_types, name):
        self.meta_types = meta_types
        self.arg_types = arg_types
        self.out_types = out_types
        self.name = name
    #def run(self, meta_args, obj_args, model, strictness):
        # strictness: 0 = postulate, 1 = benevolent to coexact, 2 = everything must be proved

        #if self.meta_types is not None:
        #    assert(len(meta_args) == len(self.meta_types))
        #    for x,t in zip(meta_args, self.meta_types): assert(isinstance(x, t))
        #if self.obj_types is not None:
        #    assert(len(obj_args) == len(self.obj_types))
        #    for x,t in zip(obj_args, self.obj_types): assert(model.obj_types[x] == t)
        #result = self.run_type_checked(meta_args, obj_types)
        #assert(len(result) == len(self.out_types))
        #for x,t in zip(result, self.out_types): assert(model.obj_types[x] == t)
        #return result

    def run(self, meta_args, obj_args, model, strictness):
        raise Exception("Not implemented")

class MovableTool(Tool):
    def __init__(self, num_eval, arg_types, out_types, name):
        Tool.__init__(self, (float, float), arg_types, out_types, name)
        self.num_eval = num_eval
        self.effects = []

    def add_effect(self, tool):
        # after tool is aplied, effects will be postulated on
        # (output, input1, input2, ...)
        self.effects.append(tool)
        
    def run(self, meta_args, obj_args, model, strictness):
        num_args = tuple(model.num_model[arg] for arg in obj_args)
        num_outs = self.num_eval(*(meta_args+num_args))
        if len(self.out_types) == 1 and not isinstance(num_outs, (list, tuple)):
            num_outs = num_outs,
        assert(len(num_outs) == len(self.out_types))
        out = model.add_objs(num_outs)
        for effect in self.effects: effect.run((), out + obj_args, model, 0)
        return out

class EqualObjects(Tool):
    def __init__(self, willingness = 0, name = "=="):
        self.willingness = willingness
        Tool.__init__(self, (), None, (), name)

    def run(self, meta_args, obj_args, model, strictness):
        assert(len(meta_args) == 0)
        a,b = obj_args
        if not (model.num_model[a] == model.num_model[b]):
            raise ToolErrorNum()
        elif strictness <= self.willingness: # postulate
            model.glue(a,b)
            return ()
        else: # check
            if model.check_equal(a,b): return ()
            else:
                print('not provably equal', a, b)
                raise ToolErrorLog()

class CachedTool:
    def __init__(self, arg_types, out_types, name):
        Tool.__init__(self, (), arg_types, out_types, name)
        self.symmetries = []
    def add_symmetry(self, perm):
        perm = tuple(perm)
        assert(set(perm) == set(range(len(perm)))) # check permutation
        assert(len(perm) == len(self.arg_types)) # check size
        # check preserved types
        perm_types = tuple(self.arg_types[i] for i in perm)
        assert(perm_types == self.arg_types)

        self.symmetries.append(perm)
        
    def get_cache(self, args, model):
        return model.get_constr(self, args)
    def set_cache(self, args, model, vals):
        model.add_constr(self, args, vals)
        for perm in self.symmetries:
            perm_args = tuple(args[i] for i in perm)
            model.add_constr(self, perm_args, vals)

    def run(self, meta_args, obj_args, model, strictness):
        # strictness: 0 = postulate, 1 = benevolent to coexact, 2 = everything must be proved

        cached = self.get_cache(obj_args, model)
        if cached is not None: return cached
        result = self.run_no_cache(obj_args, model, strictness)
        self.set_cache(obj_args, model, result)

        return result

    def run_no_cache(self, args):
        raise Exception("Not implemented")

class PrimitivePred(CachedTool):
    def __init__(self, num_check, arg_types, name, willingness = 0):
        CachedTool.__init__(self, arg_types, (), name)
        self.willingness = willingness
        self.num_check = num_check

    def run_no_cache(self, args, model, strictness):
        num_args = tuple(model.num_model[arg] for arg in args)
        if not self.num_check(*num_args): raise ToolErrorNum()
        elif strictness > self.willingness: raise ToolErrorLog()
        else: return ()

# almost the same as movable tool, just with cache
class PrimitiveConstr(CachedTool):
    def __init__(self, num_eval, arg_types, out_types, name):
        CachedTool.__init__(self, arg_types, out_types, name)
        self.num_eval = num_eval

    def run_no_cache(self, args, model, strictness):
        if strictness > 0:
            raise ToolError("Primitive construction cannot be run in check-mode")
        num_args = (model.num_model[arg] for arg in args)
        num_outs = self.num_eval(*num_args)
        if len(self.out_types) == 1 and not isinstance(num_outs, (list, tuple)):
            num_outs = num_outs,
        assert(len(num_outs) == len(self.out_types))
        return model.add_objs(num_outs)

class DimCompute(Tool):
    def __init__(self, obj_type, num_comp, postulate, name, d = None):
        Tool.__init__(self, None, None, (obj_type,), name)
        self.obj_type = obj_type
        self.num_comp = num_comp
        self.postulate = postulate
        if d is not None: d[name] = self
    def run(self, meta_args, args, model, strictness):
        coefs = meta_args[1:]
        assert(len(coefs) == len(args))

        frac_const = meta_args[0]
        obj_sum = sum(model.num_model[arg].data*float(coef)
                      for coef, arg in zip(coefs, args))
        new_obj_num = self.num_comp(obj_sum, frac_const)
        #new_obj_num = self.const_num(float(frac_const))
        #for coef, arg in zip(coefs, args):
        #    new_obj_num += model.num_model[arg].data*float(coef)
        new_obj = model.add_obj(self.obj_type(new_obj_num))

        equation = SparseRow(zip(args, coefs))
        equation[new_obj] = Fraction(-1)
        assert(all(isinstance(x, Fraction) for x in equation.values()))
        self.postulate(model, equation, frac_const)
        return (new_obj,)

class DimPred(Tool):
    def __init__(self, obj_type, num_check, postulate, check, name,
                 d = None, willingness = 0):
        self.obj_type = obj_type
        self.num_check = num_check
        self.postulate = postulate
        self.check = check
        self.willingness = willingness
        Tool.__init__(self, None, None, (), name)
        if d is not None: d[name] = self
    def run(self, meta_args, args, model, strictness):
        coefs = meta_args[1:]
        assert(len(coefs) == len(args))
        frac_const = meta_args[0]
        obj_sum = sum(model.num_model[arg].data*float(coef)
                      for coef, arg in zip(coefs, args))
        if not self.num_check(obj_sum, frac_const):
            raise ToolErrorNum()

        equation = SparseRow(zip(args, coefs))

        if strictness <= self.willingness:
            self.postulate(model, equation, frac_const)
            return ()
        elif self.check(model, equation, frac_const):
            return ()
        else: raise ToolErrorLog()
