from uf_dict import UnionFindDict

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
    def get_cache(self, args, logic_model):
        tup = (self.identifier, *args)
        return logic_model.get(tup)
    def set_cache(self, args, logic_model, result):
        tup = (self.identifier, *args)
        return logic_model.set(tup, result)
    def run(self, args, logic_model, num_model, strictness):
        # strictness: 0 = postulate, 1 = benevolent to coexact, 2 = everything must be proved

        cached = self.get_cache(args, logic_model)
        if cached is not None: return cached
        result = self.run_no_cache(args, logic_model, num_model, strictness)
        self.set_cache(args, logic_model, result)
        if hasattr(self, 'arg_permutations'):
            for perm in self.arg_permutations:
                perm_args = (args[p] for p in perm)
                self.set_cache(perm_args, logic_model, result)
        return result

class EqualObjects(Tool):
    def __init__(self, willingness = 0):
        self.willingness = willingness

    def num_check(self, num_model, a, b):
        return num_model[a] == num_model[b]

    # equality does not use cache since it is inherently implemented into the logic
    def run(self, args, logic_model, num_model, strictness):
        a,b = args
        if num_model is not None and not self.num_check(num_model, a, b):
            raise ToolErrorNum()
        elif strictness <= self.willingness: # postulate
            logic_model.glue(a,b)
            return ()
        else: # check
            if logic_model.is_equal(a,b): return ()
            else: raise ToolErrorLog()

class PrimitivePred(Tool):
    def __init__(self, num_check, extra_args = (), willingness = 0):
        self.willingness = willingness
        self.num_check = num_check
        self.extra_args = extra_args
        self.identifier = (PrimitivePred, num_check, *extra_args)

    def run_no_cache(self, args, logic_model, num_model, strictness):
        if num_model is not None:
            num_args = tuple(num_model[arg] for arg in args)
            if not self.num_check(*(self.extra_args+num_args)): raise ToolErrorNum()
            else: return ()
        elif strictness <= self.willingness: # postulate
            return ()
        else: # failed by default
            raise ToolErrorLog()

class PrimitiveConstr(Tool):
    def __init__(self, num_eval, res_types):
        self.num_eval = num_eval
        self.res_types = res_types
        self.identifier = (PrimitiveConstr, num_eval)

    def run_no_cache(self, args, logic_model, num_model, strictness):
        result = logic_model.new_objects(self.res_types)
        if num_model is not None:
            num_args = (num_model[arg] for arg in args)
            num_result = self.num_eval(*num_args)
            if len(self.res_types) == 1 and not isinstance(num_result, (list, tuple)):
                num_result = num_result,
            assert(len(num_result) == len(result))
            for t, r, num_r in zip(self.res_types, result, num_result):
                assert(type(num_r) == t)
                num_model[r] = num_r
                num_r.index = r
        return result

class CompositeTool(Tool):
    def __init__(self, steps, num_args, result):
        self.steps = steps       # step = strictness, tool, local_args
        self.num_args = num_args # arguments are local variables from range(0, num_args)
        self.result = result     # list of return values as local variables
        self.identifier = self

    def run_no_cache(self, args, logic_model, num_model, strictness):
        local_to_global = list(args)
        #print(args, self.num_args)
        assert(len(args) == self.num_args)
        for tool_strictness, tool, local_args, debug_cmd in self.steps:
            if hasattr(tool, 'name'): tool_name = tool.name
            else: tool_name = type(tool)
            global_args = tuple(local_to_global[v] for v in local_args)
            try:
                subresult = tool.run(global_args, logic_model, num_model,
                                  min(strictness, tool_strictness))
            except ToolError as e:
                e.tool_traceback.append(debug_cmd)
                raise
            local_to_global += subresult

        result = tuple(local_to_global[v] for v in self.result)
        return result
