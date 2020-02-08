#!/usr/bin/python3

from geo_object import *
from tool_step import ToolStep

def run_tuple(f, *args):
    if isinstance(f, tuple):
        args += f[1:]
        f = f[0]
    f(*args)

class GTool:
    def __init__(self, env, viewport):
        self.env = env
        self.tools = env.tools
        self.viewport = viewport
        self.distance_to_drag_pix = 5
        self.find_radius_pix = 20
        self._basic_init()
    def _basic_init(self):
        self.view_changed = True
        self.dragged = False
        self.click_coor = None

        self._pre_update()
        self._update_env_hl()
        self.update = self.update_basic

    def _update_env_hl(self):
        self.env.update_hl(
            self.hl_proposals,
            self.hl_selected,
            self.hl_helpers,
        )

    def reset(self):
        self._basic_init()
        #print("==== reset")
        #raise Exception()

    def _pre_update(self):
        self.hl_proposals = []
        self.hl_selected = []
        self.hl_helpers = []
        self.find_radius = self.find_radius_pix / self.viewport.scale
        self.drag = None
        self.confirm = None
        self.confirm_next = self.update_basic

    def hl_propose(self, *args):
        self.hl_proposals.extend(args)
    def hl_select(self, *args):
        self.hl_selected.extend(args)
    def hl_add_helper(self, *args):
        self.hl_helpers.extend(args)

    def _run_update(self, coor):
        prev_proposals = self.hl_proposals
        prev_selected = self.hl_selected
        prev_helpers = self.hl_helpers
        self._pre_update()
        run_tuple(self.update, coor)
        self.view_changed = self._check_hl_change(
            prev_proposals, prev_selected, prev_helpers
        )
        self._update_env_hl()

    def _check_hl_change(self, prev_proposals, prev_selected, prev_helpers):
        if self.view_changed: return True
        if len(prev_proposals) != len(self.hl_proposals):
            return True
        if len(prev_selected) != len(self.hl_selected):
            return True
        if len(prev_helpers) != len(self.hl_helpers):
            return True
        for a,b in zip(prev_selected, self.hl_selected):
            if a is not b: return True
        for a,b in zip(prev_proposals, self.hl_proposals):
            if not a.identical_to(b): return True
        for a,b in zip(prev_helpers, self.hl_helpers):
            if type(a) != type(b): return True
            if isinstance(a, (Line, Point)):
                if not a.identical_to(b): return True
            else:
                a1,a2 = a
                b1,b2 = b
                if not eps_identical(a1,b1) or not eps_identical(a2,b2):
                    return True
        return False

    def _run_confirm(self):
        if self.confirm is not None:
            run_tuple(self.confirm)
            self.view_changed = True
        self.update = self.confirm_next
    def button_press(self, coor):
        if self.click_coor is not None: self.reset()
        run_tuple(self.update, coor)
        if self.drag is None:
            self._run_confirm()
            self._run_update(coor)
        else:
            self.click_coor = coor
            self.dragged = False
    def button_release(self, coor):
        if self.click_coor is not None:
            click_coor = self.click_coor
            self.click_coor = None
            self.dragged = False
            self._run_confirm()
        self._run_update(coor)
    def motion(self, coor, button_pressed):
        if self.click_coor is not None:
            if not button_pressed:
                self.reset()
            elif not self.dragged:
                if np.linalg.norm(coor - self.click_coor) >= \
                   self.distance_to_drag_pix / self.viewport.scale:
                    assert(self.drag is not None)
                    self.update = self.drag
                    self.dragged = True

        if self.click_coor is None or self.dragged:
            self._run_update(coor)

    def lies_on(self, p, cl):
        p_li = self.env.gi_to_li(p)
        cl_li = self.env.gi_to_li(cl)
        if self.env.li_to_type(cl_li) == Line: label = self.tools.lies_on_l
        else: label = self.tools.lies_on_c
        return self.env.model.get_constr(label, (p_li, cl_li)) is not None

    def run_tool(self, name, *args, update = True):
        arg_types = tuple(self.env.gi_to_type(x) for x in args)
        tool = self.tools[name, arg_types]
        step = ToolStep(tool, (), args)
        return self.env.add_step(step, update = update)
    def run_m_tool(self, name, res_obj, *args, update = True):
        num_args = tuple(self.env.gi_to_num(x) for x in args)
        arg_types = tuple(type(x) for x in num_args)
        out_type = type(res_obj)
        tool = self.tools.m[name, arg_types, out_type]
        meta_args = tool.get_meta(res_obj, *num_args)
        step = ToolStep(tool, meta_args, args)
        #if name == "intersection":
        #    print(arg_types, meta_args)
        return self.env.add_step(step, update = update)

    def coor_to_obj(self, coor, lists, avoid = None):
        candidates = []
        for l in lists:
            if not l: continue
            candidate = min((
                (objn.dist_from(coor), obj, objn)
                for (obj,objn) in l
            ), key = lambda x: x[0])
            if candidate[0] >= self.find_radius: continue
            if avoid is not None and avoid(*candidate[1:]): continue
            if l is self.env.selectable_points: return candidate[1:]
            candidates.append(candidate)
        if not candidates: return None, None
        return min(candidates, key = lambda x: x[0])[1:]

    def coor_to_point(self, coor, **kwargs):
        return self.coor_to_obj(coor, (self.env.selectable_points,), **kwargs)
    def coor_to_line(self, coor, **kwargs):
        return self.coor_to_obj(coor, (self.env.selectable_lines,), **kwargs)
    def coor_to_circle(self, coor, **kwargs):
        return self.coor_to_obj(coor, (self.env.selectable_circles,), **kwargs)
    def coor_to_cl(self, coor, **kwargs):
        return self.coor_to_obj(
            coor, (self.env.selectable_lines,self.env.selectable_circles), **kwargs)
    def coor_to_pc(self, coor, **kwargs):
        return self.coor_to_obj(
            coor, (self.env.selectable_points,self.env.selectable_circles), **kwargs)
    def coor_to_pl(self, coor, **kwargs):
        return self.coor_to_obj(
            coor, (self.env.selectable_points,self.env.selectable_lines), **kwargs)
    def coor_to_pcl(self, coor, **kwargs):
        return self.coor_to_obj(coor, (
            self.env.selectable_points, self.env.selectable_lines,
            self.env.selectable_circles
        ), **kwargs)
    
    # to be implemented
    def update_basic(self, coor):
        pass

class GToolMove(GTool):
    def __init__(self, *args):
        GTool.__init__(self, *args)
        self.distance_to_drag_pix = 0

    def update_basic(self, coor):
        obj = self.env.select_movable_obj(coor, self.viewport.scale)
        if obj is None: return

        self.hl_select(obj)
        step = self.env.gi_to_step(obj)
        num_args = tuple(self.env.gi_to_num(gi) for gi in step.local_args)
        num_res = self.env.gi_to_num(obj),
        grasp = step.tool.get_grasp(coor, *num_args+num_res)
        self.drag = self.move_obj, step, grasp, num_args

    def move_obj(self, coor, step, grasp, num_args):
        step.meta_args = step.tool.new_meta(grasp, coor, *num_args)
        self.env.refresh_steps(catch_errors = True)

class GToolHide(GTool):

    def update_basic(self, coor):
        obj,_ = self.coor_to_pcl(coor)
        if obj is None: return

        self.hl_select(obj)
        self.confirm = self.hide_obj, obj

    def hide_obj(self, obj):
        self.env.hide(obj)
