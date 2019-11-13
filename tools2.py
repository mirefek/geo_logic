class ToolError(Exception):
    def __init__(self, *args, **kwargs):
        self.tool_traceback = []
        Exception.__init__(self, *args, **kwargs)
    def __str__(self):
        msg = Exception.__str__(self)
        return "{}\n Tool traceback:\n  ".format(msg)+"\n  ".join(
            "{}: {}".format(cmd.line_n, cmd.line)
            for cmd in self.tool_traceback
        )

class ToolErrorNum(ToolError):
    def __init__(self):
        ToolError.__init__(self, "Numerical check failed")
class ToolErrorLog(ToolError):
    def __init__(self):
        ToolError.__init__(self, "Fact not supported by logic")

class Tool:
    def __init__(self, meta_len, obj_types, out_types):
        self.meta_types = meta_types
        self.obj_types = obj_types
        self.out_types = out_types
    def run(self, meta_args, obj_args, model, strictness):
        # strictness: 0 = postulate, 1 = benevolent to coexact, 2 = everything must be proved

        assert(len(meta_args) == len(self.meta_len))
        for x,t in zip(meta_args, self.meta_types): assert(isinstance(x, t))
        assert(len(obj_args) == len(self.obj_types))
        for x,t in zip(obj_args, self.obj_types): assert(model.obj_types[x] == t)
        result = self.run_type_checked(meta_args, obj_types)
        assert(len(result) == len(self.out_types))
        for x,t in zip(result, self.out_types): assert(model.obj_types[x] == t)
        return result

    def run_type_checked(self, meta_args, obj_args, model, strictness):
        raise Exception("Not implemented")

class MovableTool(Tool):
    def __init__(self, num_eval, arg_types, out_types):
        Tool.__init__(self, (float, float), arg_types)
        self.num_eval = num_eval

    def run_type_checked(self, meta_args, obj_args, model, strictness):
        np_point = np.array(meta_args)
        num_args = (model.num_model[arg] for arg in args)
        num_outs = self.num_eval(np_point, *num_args)
        if len(self.out_types) == 1 and not isinstance(num_result, (list, tuple)):
            num_result = num_result,
        assert(len(num_outs) == len(self.out_types))
        return model.new_add_objs(num_outs)

class EqualObjects(Tool):
    def __init__(self, willingness = 0):
        self.willingness = willingness
        Tool.__init__(self, (), None, ())

    # run_type_checked skipped because of polymorphicity of equality
    def run(self, meta_args, obj_args, model, strictness):
        assert(not meta_args)
        a,b = obj_args
        if not (model.num_model[a] == model.num_model[b]):
            raise ToolErrorNum()
        elif strictness <= self.willingness: # postulate
            model.glue(a,b)
            return ()
        else: # check
            if model.is_equal(a,b): return ()
            else: raise ToolErrorLog()

class CachedTool:
    def __init__(self, obj_types, out_types):
        Tool.__init__(self, (), arg_types, out_types)
    def get_cache(self, args, model):
        return model.get_constr(self, args)
    def set_cache(self, args, model, vals):
        return model.add_constr(self, args, vals)
    def run_type_checked(self, meta_args, obj_args, model, strictness):
        # strictness: 0 = postulate, 1 = benevolent to coexact, 2 = everything must be proved

        cached = self.get_cache(obj_args, model)
        if cached is not None: return cached
        result = self.run_no_cache(obj_args, model, strictness)
        self.set_cache(obj_args, model, result)

        return result

    def run_no_cache(self, args):
        raise Exception("Not implemented")

class PrimitivePred(CachedTool):
    def __init__(self, num_check, arg_types, willingness = 0):
        CachedTool.__init__(self, arg_types, ())
        self.willingness = willingness
        self.num_check = num_check

    def run_no_cache(self, args, model, strictness):
        if num_model is not None:
            num_args = tuple(model.num_model[arg] for arg in args)
            if not self.num_check(*num_args): raise ToolErrorNum()
            else: return ()
        elif strictness <= self.willingness: # postulate
            return ()
        else: # failed by default
            raise ToolErrorLog()

# almost the same as movable tool, just with cache
class PrimitiveConstr(CachedTool):
    def __init__(self, num_eval, arg_types, out_types):
        CachedTool.__init__(self, arg_types, out_types)
        self.num_eval = num_eval

    def run_no_cache(self, args, model, strictness):
        num_args = (model.num_model[arg] for arg in args)
        num_outs = self.num_eval(*num_args)
        if len(self.out_types) == 1 and not isinstance(num_result, (list, tuple)):
            num_result = num_result,
        assert(len(num_outs) == len(self.out_types))
        return model.new_add_objs(num_outs)

class CompositeTool(CachedTool):
    def __init__(self, assumptions, implications, result, proof, arg_types, out_types):
        CachedTool.__init__(arg_types, out_types)
        self.assumptions = assumptions
        self.implications = implications
        self.result = results
        self.proof = proof

        self.deep_len = self._deep_len_of(assumptions) + \
            len(implications) + _deep_len_of(proof)

    def _deep_len_of(cmd_list):
        deep_len = 0
        for tool, meta_args, local_args, debug_msg in cmd_list:
            if isinstance(tool, CompositeTool): deep_len += tool.deep_len
            else: deep_len += 1
        return deep_len

    def _run_commands(cmd_list. strictness, model, local_to_global):
        for tool, meta_args, local_args, debug_cmd in cmd_list:
            global_args = tuple(local_to_global[v] for v in local_args)
            try:
                subresult = tool.run(global_args, logic_model, num_model,
                                  min(strictness, tool_strictness))
            except ToolError as e:
                e.tool_traceback.append(debug_cmd)
                raise
            local_to_global.extend(subresult)

    def run_no_cache(self, args, model, strictness):
        local_to_global = list(args)
        self._run_commands(self.assumptions, strictness, model, local_to_global)
        self._run_commands(self.implication, 0, model, local_to_global)

        result = tuple(local_to_global[v] for v in self.result)
        return result

# !!! TODO:
class DimTool(Tool):
    def __init__(self, dim_type, coefs, frac_const, num_outputs, willingness = 0):
        Tool.__init__((), [dim_type]*len(coefs), [dim_type]*num_outputs)
        self.coefs = coefs
        self.frac_const = frac_const
        self.willingness = willingness

    def raw_value(self, num_model):
        if len(self.coefs) == 0: return self.zero
        return self.num_type(sum(
            float(coef)*to_num(x) for (x,coef) in sr.items()
        ))

    def make_equation(self, args, model):
        sr = SparseRow(())
        sr += (
            (arg, coef)
            for arg, coef in zip(args, self.coefs)
        )
        return sr
    
    def check_zero(self, args, logic_model, num_model, strictness):
        equation, matrix = self.prepare_data(args, logic_model)
        if num_model is not None:
            if self.value(num_model, equation) != self.zero:
                raise ToolErrorNum()
        if strictness <= self.willingness: # postulate
            logic_model.add_eq(matrix, equation)
        else: # check
            #matrix.print_self()
            #print(equation)
            #print(matrix.query(equation))
            if matrix.query(equation): return ()
            else: raise ToolErrorLog()

    def construct(self, args, logic_model, num_model, willingness):
        equation, matrix = self.prepare_data(args, logic_model)
        result = logic_model.new_object(self.num_type)
        logic_model.add_eq(matrix, equation - to_dim(result))

        if num_model is not None:
            num_model[result] = self.value(num_model, equation)
        return result,
