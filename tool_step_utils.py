from logical_core import LogicalCore
from tools import ToolError
from tool_step import ToolStep, ToolStepEnv, CompositeTool

def check_steps(steps, goals, imported_tools):
    logic = LogicalCore(basic_tools = imported_tools)
    step_env = ToolStepEnv(logic)

    try:
        step_env.run_steps(steps, 0, catch_errors = False)
        step_env.run_steps(goals, 0, catch_errors = False)
        return True
    except ToolError:
        return False

def compute_num_objs(steps, imported_tools):
    logic = LogicalCore(basic_tools = imported_tools)
    step_env = ToolStepEnv(logic)
    step_env.run_steps(steps, 0, catch_errors = False)
    return [logic.num_model[li] for li in step_env.local_to_global]

def copy_steps(steps):
    return [
        ToolStep(
            tool = step.tool,
            hyper_params = step.hyper_params,
            local_args = step.local_args,
            start_out = step.start_out,
            debug_msg = step.debug_msg,
        )
        for step in steps
    ]

def steps_var_replace(steps, old_to_new):
    new_steps = []
    for step in steps:
        new_local_args = tuple(old_to_new[x] for x in step.local_args)
        new_step = ToolStep(step.tool, step.hyper_params, new_local_args,
                            step.start_out, step.debug_msg)
        new_steps.append(new_step)

    return new_steps

def merge_duplicities(steps, imported_tools):
    logic = LogicalCore(basic_tools = imported_tools)
    step_env = ToolStepEnv(logic)
    step_env.run_steps(steps, 0, catch_errors = False)
    global_to_local = dict()
    old_to_new = []
    for loc, glob in enumerate(step_env.local_to_global):
        glob = logic.ufd.obj_to_root(glob)
        old_to_new.append(global_to_local.setdefault(glob, loc))

    new_steps = steps_var_replace(steps, old_to_new)
    for step in steps:
        new_local_args = tuple(old_to_new[x] for x in step.local_args)
        new_step = ToolStep(step.tool, step.hyper_params, new_local_args,
                            len(old_to_new), step.debug_msg)
        new_steps.append(new_step)

    return new_steps, old_to_new

def remove_redundant(steps, outputs):
    obj_to_step = []
    for i,step in enumerate(steps):
        obj_to_step.extend([i]*len(step.tool.out_types))
    used = [False]*len(steps)
    stack = list(outputs)
    while stack:
        obj = stack.pop()
        step_i = obj_to_step[obj]
        if used[step_i]: continue
        used[step_i] = True
        stack.extend(steps[step_i].local_args)

    new_steps = []
    old_to_new = dict()
    obj_index = 0
    for step,u in zip(steps, used):
        if not u: continue
        new_local_args = tuple(old_to_new[x] for x in step.local_args)
        new_step = ToolStep(step.tool, step.hyper_params, new_local_args,
                            obj_index, step.debug_msg)
        obj_index += len(step.tool.out_types)
        old_to_new.update(zip(step.local_outputs, new_step.local_outputs))
        new_steps.append(new_step)

    return new_steps, old_to_new, used

def expand_step(steps, expand_predicate):

    old_to_new = []
    obj_index = 0
    new_steps = []
    for step_i, step in enumerate(steps):
        new_local_args = tuple(old_to_new[x] for x in step.local_args)
        if expand_predicate(step_i, step):
            assert isinstance(step.tool, CompositeTool)
            assert not step.tool.implications
            assert not step.tool.proof

            subvars = list(new_local_args)
            for substep in step.tool.assumptions:
                sub_local_args = tuple(subvars[x] for x in substep.local_args)
                new_substep = ToolStep(
                    substep.tool, substep.hyper_params, sub_local_args,
                    obj_index, substep.debug_msg,
                )
                new_steps.append(new_substep)
                out_len = len(substep.tool.out_types)
                subvars.extend(range(obj_index, obj_index+out_len))
                obj_index += out_len

            old_to_new.extend(subvars[x] for x in step.tool.result)
        else:
            new_step = ToolStep(step.tool, step.hyper_params, new_local_args,
                                obj_index, step.debug_msg)
            obj_index += len(step.tool.out_types)
            old_to_new.extend(new_step.local_outputs)
            new_steps.append(new_step)

    return new_steps, old_to_new
