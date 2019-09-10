from uf_dict import UnionFindDict
from dim_tool import degree
from sparse_elim import ElimMatrixI, ElimMatrixF
from tool_base import CompositeTool, ToolError
import geo_object as gt

class LogicModel(UnionFindDict):
    def __init__(self):
        super(LogicModel, self).__init__()
        self.obj_types = []
        self.angles = ElimMatrixI()
        self.angles.add(180*degree)
        self.ratios = ElimMatrixF()

    def glueable(self, obj):
        return isinstance(obj, int) and obj >= 0

    def add_eq(self, matrix, equation):
        #print("add_eq", equation)
        to_glue = matrix.add(equation)[1]
        #to_glue = ((a,b) for (a,b) in to_glue
        #           if a >= 0 and b >= 0)
        self.multi_glue(*to_glue)
        #matrix.print_self()
        #print(matrix.query(equation))
        #print("to_glue", to_glue)
    def glue_hook(self, n1, n2, to_glue):
        def extend(new_pairs):
            to_glue.extend(
                (a,b) for (a,b) in new_pairs
                if a >= 0 and b >= 0
            )
        if issubclass(self.get_type(n1), gt.Angle):
            assert issubclass(self.get_type(n2), gt.Angle)
            to_glue.extend(self.angles.glue(n1, n2)[1])
        elif issubclass(self.get_type(n1), gt.Ratio):
            assert issubclass(self.get_type(n2), gt.Ratio)
            to_glue.extend(self.ratios.glue(n1, n2)[1])

    def get_type(self, obj):
        return self.obj_types[obj]
    def new_objects(self, types):
        next_index = len(self.obj_types)
        result = list(range(next_index, next_index + len(types)))
        self.obj_types.extend(types)
        return result
    def new_object(self, t):
        return self.new_objects((t,))[0]
    def new_num_object(self, num_obj, num_model):
        log_obj = self.new_object(type(num_obj))
        num_obj.index = log_obj
        num_model[log_obj] = num_obj
        return log_obj

def compose_tool(steps, arg_types, final_result, check_validity = True):
    # steps: is_assumption, tool, local_args

    if check_validity:
        logic_model = LogicModel()
        objs = logic_model.new_objects(arg_types)
        #print(steps)
        for is_assumption, tool, local_args, debug_cmd in steps:
            strictness = int(not is_assumption)
            args = tuple(objs[i] for i in local_args)
            if hasattr(tool, 'name'): tool_name = tool.name
            else: tool_name = type(tool)
            try:
                subresult = tool.run(args, logic_model, None, strictness)
            except ToolError as e:
                e.tool_traceback.append(debug_cmd)
                raise
            if subresult is None: return None
            objs.extend(subresult)

        del logic_model

    res_steps = [
        (1, tool, args, debug_data)
        for (_, tool, args, debug_data) in steps
    ]
    return CompositeTool(res_steps, len(arg_types), final_result)
