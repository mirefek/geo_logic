from fractions import Fraction
from tools import CachedTool, ToolError, DimCompute, DimPred, ToolErrorException
from logic_model import LogicModel
from geo_object import Point

class ToolStep:
    __slots__ = ["tool", "meta_args", "local_args", "debug_msg"]
    def __init__(self, tool, meta_args, local_args, debug_msg = None):
        self.tool = tool
        if isinstance(tool, (DimCompute, DimPred)):
            self.meta_args = tuple(Fraction(x) for x in meta_args)
        else: self.meta_args = tuple(meta_args)
        self.local_args = tuple(local_args)
        self.debug_msg = debug_msg

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
    def __init__(self, assumptions, implications, result, proof, arg_types, out_types, name, triggers = None):
        CachedTool.__init__(self, arg_types, out_types, name)
        self.assumptions = assumptions
        self.implications = implications
        self.result = result
        self.proof = proof
        self.proof_triggers = triggers

        self.deep_len_all = sum(
            step.tool.deep_len_all
            for step in assumptions
            if isinstance(step.tool, CompositeTool)
        )
        if proof is None:
            self.deep_len_proof = 0
        else:
            self.deep_len_proof = 1 + sum(
                step.tool.deep_len_all
                for step in implications + proof
                if isinstance(step.tool, CompositeTool)
            )
            self.deep_len_all += self.deep_len_proof

    def run_no_cache(self, args, model, strictness):
        env = ToolStepEnv(model, args)
        env.run_steps(self.assumptions, strictness)
        if strictness == 1 and self.proof is not None:
            num_args = [
                model.num_model[gi]
                for gi in env.local_to_global
            ]
            proof_checker.check(self, num_args)
        env.run_steps(self.implications, 0)

        result = tuple(env.local_to_global[v] for v in self.result)
        return result

    def proof_check(self, num_args):
        assert(self.proof is not None)
        model = LogicModel(triggers = self.proof_triggers)
        args = model.add_objs(num_args[:len(self.arg_types)])
        env = ToolStepEnv(model, args)
        try:
            env.run_steps(self.assumptions, 0)
            #for num_arg, gi in zip(num_args, env.local_to_global):
            #    if not num_arg.identical_to(model.num_model[gi]):
            #        raise ToolError("Extracted problem leads to different numerical values")

            local_to_global_bak = list(env.local_to_global)
            env.run_steps(self.proof, 1)
            env.local_to_global = local_to_global_bak
            env.run_steps(self.implications, 1)
        except ToolError as e:
            e.tool_traceback.append(
                "Failed proof: {} {}".format(self.name, num_args[:len(self.arg_types)])
            )
            raise

import threading
from queue import Queue, Empty
from collections import deque
import time

class ProofChecker:
    def __init__(self):
        self.t = threading.Thread(target=self.process, daemon = True)
        self.q = Queue()
        self.stack = []
        self.checked_num = 0
        self.task_index = 0
        self.tasks = []

    def paralelize(self, progress_hook = None):
        self.progress_hook = progress_hook
        self.t.start()
    #def start(self):
    #    self.t.start()
    #def stop(self):
    #    self.q.put((None, "stop"))
    #    self.t.join()

    def check(self, tool, num_args):
        if not self.t.is_alive():
            tool.proof_check(num_args)
            return
        if threading.current_thread() != self.t:
            self.q.put((tool, num_args))
        else:
            self.stack.append((tool, num_args))
            #print("  |{}+ adding {} [{}:{}]...".format(
            #    '  '*len(self.stack), tool.name,
            #    tool.deep_len_proof,tool.deep_len_all,
            #))

    def reset(self):
        self.q.put((None, "reset"))

    def read_queue(self, block):
        tool, args = self.q.get(block)
        if tool is not None:
            self.tasks.append((tool, args))
            #print("to_check", tool.name, tool.deep_len_proof)
            #print("from queue:", tool.name)
        elif args == "reset":
            self.stack = []
            self.tasks = []
            self.task_index = 0
            self.time = time.time()
            self.checked_num = 0

    def update_progress(self):
        if self.progress_hook is None: return
        remains = sum(tool.deep_len_proof for (tool,_) in self.stack + self.tasks[self.task_index:])
        size = sum(tool.deep_len_proof for (tool,_) in self.tasks)
        self.progress_hook(size - remains, size)

    def process(self):
        sleepiness = 0
        while True:
            while not self.q.empty():
                self.read_queue(False)
            while not self.stack and self.task_index >= len(self.tasks):
                self.task_index = 0
                self.tasks = []
                self.update_progress()
                self.read_queue(True)
            if not self.stack and self.task_index < len(self.tasks):
                self.stack.append(self.tasks[self.task_index])
                self.task_index += 1

            if sleepiness == 5:
                sleepiness = 0
                self.update_progress()
                time.sleep(0.01) # prevent GUI from lagging
            else: sleepiness += 1

            tool, num_args = self.stack.pop()
            try:
                self.checked_num += 1
                tool.proof_check(num_args)
            except ToolError as e:
                print("Proof check failed: {}".format(e))
            if not self.stack and self.task_index == len(self.tasks):
                print("DONE [{}:{}] {}".format(
                    self.checked_num, sum(tool.deep_len_proof for (tool, _) in self.tasks),
                    time.time() - self.time,
                ))

proof_checker = ProofChecker()
