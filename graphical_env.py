from tool_step import ToolStepEnv, CompositeTool, proof_checker
from logical_core import LogicalCore
from geo_object import *
import itertools
from tools import ToolError, ToolErrorException
from knowledge_visualisation import KnowledgeVisualisation

"""
GraphicalEnv contains primarily the list of the main steps
in the construction constructed in GUI, and the state of logic
after the constructions steps.
As additional data, it contains names of the objects and redo stack.
The state of the logical core is processed using
KnowledgeVisualisation contained in the GraphicalEnv to extract
the data to be drawn.

The logical core self.logic is contained in a StepEnv: self.step_env.

The objects here are primarily viewed as "GUI indices" (gi)
which correspond to local indices in a StepEnv. There are also
"logical indices" (li) that correcpond to the global indices in
StepEnv and represent the object in the logical core.
"""

# "smart" assignment of a name of a new object
def make_name(step, out_i, t, used_names):
    tool = step.tool
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

        # build logic and step_env
        self.refresh_steps()

        # hooks
        self.add_step_hook = lambda step: None
        self.remove_step_hook = lambda step: None
        self.reload_steps_hook = lambda steps: None
        self.update_hyperpar_hook = lambda step: None

    # given gi, return index of a step which created it
    def gi_to_step(self, gi):
        i = self.gi_to_step_i[gi]
        return self.steps[i]

    # change name of a gi, and check name collisions
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
    
    # on loading a file / reseting
    def set_steps(self, steps, names, goals = None, proof = None):
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
        assert(len(self.gi_to_name) == len(self.gi_to_step_i))
        #self.refresh_steps(False)
        self.refresh_steps()
        self.reload_steps_hook()
        self.redo_stack = []

    def add_step(self, step, update = True):
        # update = False if we will immediatelly add another steps
        try:
            ori_len = len(self.step_env.local_to_global)
            self.step_env.run_steps((step,), 1)
            new_len = len(self.step_env.local_to_global)
            self.gi_to_step_i += [len(self.steps)]*len(step.tool.out_types)
            self.vis.add_gis(len(step.tool.out_types))
            for i,t in enumerate(step.tool.out_types):
                used_names = set(self.gi_to_name)
                name = make_name(step, i, t, used_names)
                self.gi_to_name.append(name)
                used_names.add(name)
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

    def pop_step(self): # undo
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

    # reset the logical core and run all steps (with all proof checks)
    def refresh_steps(self, catch_errors = True):
        proof_checker.reset()
        self.logic = LogicalCore(basic_tools = self.tools)
        self.step_env = ToolStepEnv(self.logic)
        self.vis.set_logic(self.logic, self.step_env.local_to_global)
        self.step_env.run_steps(self.steps, 1, catch_errors = catch_errors)
        self.check_goals()
        self.vis.refresh()
    def check_goals(self):
        if self.goals is None: return
        self.step_env.run_steps(self.goals, 1, catch_errors = True)
        if all(goal.success for goal in self.goals):
            print("Goals accomplished")
        else: print("Goals are not accomplished yet...")
