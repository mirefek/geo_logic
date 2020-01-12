from fractions import Fraction
from tools import CachedTool, ToolError, DimCompute, DimPred, ToolErrorException

class ToolStep:
    __slots__ = ["tool", "meta_args", "local_args", "debug_msg"]
    def __init__(self, tool, meta_args, local_args, debug_msg = None):
        self.tool = tool
        if isinstance(tool, (DimCompute, DimPred)):
            self.meta_args = tuple(Fraction(x) for x in meta_args)
        else: self.meta_args = tuple(meta_args)
        self.local_args = tuple(local_args)
        self.debug_msg = debug_msg

def deep_len_of(steps):
    deep_len = 0
    for step in steps:
        if isinstance(step.tool, CompositeTool): deep_len += step.tool.deep_len
        else: deep_len += 1
    return deep_len

class ToolStepEnv:
    def __init__(self, logic_model, ini_vars = ()):
        self.model = logic_model
        self.local_to_global = list(ini_vars)

    def run_steps(self, steps, strictness, catch_errors = False):
        for step in steps:
            global_args = tuple(self.local_to_global[v] for v in step.local_args)
            subresult = [None]*len(step.tool.out_types)
            if None not in global_args:
                try:
                    subresult = step.tool.run(step.meta_args, global_args, self.model, strictness)
                except Exception as e:
                    if not isinstance(e, ToolError): e = ToolErrorException(e)
                    if step.debug_msg is not None: e.tool_traceback.append(step.debug_msg)
                    if catch_errors:
                        print("Construction error: {}".format(e))
                    else: raise e
            self.local_to_global.extend(subresult)

class CompositeTool(CachedTool):
    def __init__(self, assumptions, implications, result, proof, arg_types, out_types):
        CachedTool.__init__(self, arg_types, out_types)
        self.assumptions = assumptions
        self.implications = implications
        self.result = result
        self.proof = proof

        self.deep_len = deep_len_of(assumptions) + \
            len(implications) + deep_len_of(proof)

    def run_no_cache(self, args, model, strictness):
        env = ToolStepEnv(model, args)
        env.run_steps(self.assumptions, strictness)
        env.run_steps(self.implications, 0)

        result = tuple(env.local_to_global[v] for v in self.result)
        return result
