from geo_object import GeoObject
from logic_model import LogicModel
from tool_base import ToolError, PrimitivePred
from geo_object import Point
import primitive_pred

class Construction:
    def __init__(self):
        self.steps = []
        self.num_model = dict()
        self.logic_model = LogicModel()
        self.to_constr_index_d = dict()
        self.visible_ci = set()
        self.visible_li = set()

    def to_constr_index(self, obj):
        if isinstance(obj, GeoObject): obj = obj.index
        candidates = { obj }
        candidates.update(self.logic_model.obj_to_children[obj])
        for cand in sorted(candidates):
            ci = self.to_constr_index_d.get(cand, None)
            if ci is not None and ci in self.visible_ci:
                return ci
        raise Exception(
            "object {} not found in construction".format(obj))

    def to_log_index(self, ci):
        step_i, out_i = ci
        output = self.steps[step_i].output
        if output is None: return None
        return self.logic_model.obj_to_root(output[out_i])

    def update_visible(self):
        self.visible_li = set(
            map(self.to_log_index, self.visible_ci))

    def refresh(self):
        self.num_model = dict()
        self.logic_model = LogicModel()
        self.to_constr_index_d = dict()

        for i, step in enumerate(self.steps):
            try: step._apply()
            except ToolError as e:
                step.result = None
                print("Step {} failed, details: {}".format(i, e))

        self.update_visible()

    def pop(self):
        removed_visible = False
        while not removed_visible:
            if len(self.steps) == 0:
                print("No more steps to undo")
                break
            s = self.steps.pop()
            for i in range(s.out_len):
                ci = s.step_i, i
                if ci in self.visible_ci:
                    self.visible_ci.remove(ci)
                    removed_visible = True
        self.refresh()

    def hide(self, obj):
        if isinstance(obj, GeoObject): obj = obj.index
        candidates = { obj }
        candidates.update(self.logic_model.obj_to_children[obj])
        for cand in sorted(candidates):
            ci = self.to_constr_index_d.get(cand, None)
            if ci is not None:
                self.visible_ci.discard(ci)
        self.update_visible()

class ConstrStep:
    def __init__(self, constr, *args):
        self.args = tuple(map(constr.to_constr_index, args))
        self.constr = constr
        self.step_i = len(constr.steps)
        try:
            self._apply()
            for out_i, obj in enumerate(self.output):
                ci = self.step_i, out_i
                self.constr.visible_ci.add(ci)
            constr.steps.append(self)
            constr.update_visible()
        except ToolError as e:
            print("New step failed, details: {}".format(e))
            constr.refresh()

    def _apply(self):
        # get the right indices as args
        args = tuple(map(self.constr.to_log_index, self.args))
        if args is None: self.output = None
        else:
            self.output = self.apply(*args)
            for out_i, obj in enumerate(self.output):
                ci = self.step_i, out_i
                self.constr.to_constr_index_d[obj] = ci
            self.out_len = len(self.output)

class ConstrMovable(ConstrStep):
    def __init__(self, constr, coor, *args):
        self.coor = coor
        ConstrStep.__init__(self, constr, *args)

class ConstrFreePoint(ConstrMovable):
    def apply(self):
        return self.constr.logic_model.new_num_object(
            Point(self.coor), self.constr.num_model),

class ConstrDepPoint(ConstrMovable):
    def apply(self, ps_index):
        ps_num = self.constr.num_model[ps_index]
        true_coor = ps_num.closest_on(self.coor)
        res_index = self.constr.logic_model.new_num_object(
            Point(true_coor), self.constr.num_model)
        lies_on_id = (PrimitivePred, primitive_pred.lies_on)
        self.constr.logic_model.set((lies_on_id, res_index, ps_index))

        return res_index,

class ConstrTool(ConstrStep):
    def __init__(self, constr, tool, args):
        self.tool = tool
        ConstrStep.__init__(self, constr, *args)

    def apply(self, *args):
        return self.tool.run(
            args,
            self.constr.logic_model,
            self.constr.num_model,
            strictness = 1
        )
