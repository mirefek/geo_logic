from tool_step import ToolStepEnv, CompositeTool, proof_checker
from logic_model import LogicModel
from geo_object import *
import itertools
from tools import ToolError, ToolErrorException
from knowledge_visualisation import KnowledgeVisualisation

class GraphicalEnv:

    def __init__(self, tools):

        self.tools = tools
        self.vis = KnowledgeVisualisation(self)

        self.redo_stack = []

        self.steps = []
        self.min_steps = 0
        self.goals = None
        self.gi_to_step_i = []
        self.gi_to_name = []

        self.refresh_steps()

        # hooks
        self.add_step_hook = lambda step: None
        self.remove_step_hook = lambda step: None
        self.reload_steps_hook = lambda steps: None
        self.update_meta_hook = lambda step: None

    def gi_to_step(self, gi):
        i = self.gi_to_step_i[gi]
        return self.steps[i]

    def change_name(self, gi, name):
        if name == self.gi_to_name[gi]: return
        problems = []
        
        if ':' in name:
            problems.append("Name cannot contain ':'")
        if not name[:1].isalpha():
            problems.append("Name must start with a letter of alphabet")
        if any(c.isspace() for c in name):
            problems.append("Name cannot contain space characters")
        if problems:
            print("Warning: Cannot use name \"{}\":".format(name))
            for problem in problems: print('  ', problem)
            return
        if name in self.gi_to_name:
            gi2 = self.gi_to_name.index(name)
            self.gi_to_name[gi2] = self.gi_to_name[gi]
        self.gi_to_name[gi] = name
        self.vis.update_selected_hook()
    
    def set_steps(self, steps, names, visible = None, goals = None, proof = None):
        self.vis.truncate_gis(0)
        if goals is None: self.min_steps = 0
        else:
            self.min_steps = len(steps)
            if proof is not None: steps = steps + proof
        self.goals = goals
        self.steps = list(steps)
        self.gi_to_name = list(names)
        self.gi_to_step_i = []
        for i,step in enumerate(steps):
            self.gi_to_step_i += [i]*len(step.tool.out_types)
        self.vis.add_gis(len(self.gi_to_step_i))
        if visible is not None:
            self.vis.set_visible_set(visible)
        assert(len(self.gi_to_name) == len(self.gi_to_step_i))
        self.refresh_steps(False)
        self.reload_steps_hook()
        self.redo_stack = []

    def make_name(self, step, out_i, t):
        tool = step.tool
        used_names = set(self.gi_to_name)
        if isinstance(tool, CompositeTool) and tool.var_to_name is not None:
            candidate = tool.var_to_name.get(tool.result[out_i], None)
            #print("Candidate:", candidate)
            if candidate is not None and candidate not in used_names:
                return candidate
        if t == Point:
            i = -1
            while True:
                for c in range(ord('A'), ord('Z')+1):
                    if i < 0: candidate = chr(c)
                    else: candidate = chr(c)+str(i)
                    if candidate not in used_names: return candidate
                i += 1
        elif t == Angle:
            i = 0
            while True:
                candidate = "ang"+str(i)
                if candidate not in used_names: return candidate
                i += 1
        elif t == Ratio:
            i = 0
            while True:
                candidate = "d"+str(i)
                if candidate not in used_names: return candidate
                i += 1
        else:
            i = -1
            while True:
                for c in range(ord('a'), ord('z')+1):
                    if i < 0: candidate = chr(c)
                    else: candidate = chr(c)+str(i)
                    if candidate not in used_names: return candidate
                i += 1

    def add_step(self, step, update = True):
        try:
            ori_len = len(self.step_env.local_to_global)
            self.step_env.run_steps((step,), 1)
            new_len = len(self.step_env.local_to_global)
            self.gi_to_step_i += [len(self.steps)]*len(step.tool.out_types)
            self.vis.add_gis(len(step.tool.out_types))
            for i,t in enumerate(step.tool.out_types):
                self.gi_to_name.append(self.make_name(step, i, t))
            self.steps.append(step)
            self.add_step_hook(step)
            self.redo_stack = []
            if update:
                self.check_goals()
                self.vis.refresh()
            print("Applied: {}".format(step.tool.name))
            return tuple(range(ori_len, new_len))
        except ToolError as e:
            if isinstance(e, ToolErrorException): raise e.e
            print("Tool '{}' failed: {}".format(step.tool.name, e))
            self.refresh_steps()
            return None

    def pop_step(self):
        if len(self.steps) == self.min_steps:
            print("No more steps to undo")
            return
        step = self.steps.pop()
        self.remove_step_hook(step)
        print("Undo {}".format(step.tool.name))
        names = ()
        if len(step.tool.out_types) > 0:
            i = len(self.gi_to_step_i)-len(step.tool.out_types)
            names = self.gi_to_name[i:]
            del self.gi_to_name[i:]
            del self.gi_to_step_i[i:]
            self.vis.truncate_gis(i)
        self.redo_stack.append((step, names))
        self.refresh_steps()
    def redo(self):
        if not self.redo_stack:
            print("Redo stack is empty")
            return
        step,names = self.redo_stack.pop()
        print("Redo {}".format(step.tool.name))

        self.gi_to_step_i += [len(self.steps)]*len(step.tool.out_types)
        self.vis.add_gis(len(step.tool.out_types))
        self.gi_to_name.extend(names)
        self.steps.append(step)
        self.step_env.run_steps((step,), 1, catch_errors = True)
        self.check_goals()

        self.vis.refresh()
        self.add_step_hook(step)

    def refresh_steps(self, catch_errors = True):
        proof_checker.reset()
        self.model = LogicModel(basic_tools = self.tools)
        self.step_env = ToolStepEnv(self.model)
        self.vis.set_model(self.model, self.step_env.local_to_global)
        self.step_env.run_steps(self.steps, 1, catch_errors = catch_errors)
        self.check_goals()
        self.vis.refresh()
    def check_goals(self):
        if self.goals is None: return
        self.step_env.run_steps(self.goals, 1, catch_errors = True)
        if all(goal.success for goal in self.goals):
            print("Goals accomplished")
        else: print("Goals are not accomplished yet...")
