from geo_object import Point, Line, Circle
from gtool import GTool
from tools import Tool
from tool_step import ToolStep
from collections import defaultdict
from parse import Parser, type_to_c

class GToolDict:
    def __init__(self, tool_dict):
        self.name_to_prefixes = defaultdict(dict)
        for (name, arg_types), tool in tool_dict.items():
            if arg_types is None: continue
            if name.startswith("prim__"): continue
            if not all(
                issubclass(arg, (Point, Line, Circle))
                for arg in arg_types
            ): continue
            if len(arg_types) == 0: continue
            prefix_d = self.name_to_prefixes[name]
            prefix_d[arg_types] = tool
            for i,t in enumerate(arg_types):
                prefix = tuple(arg_types[:i])
                type_set = prefix_d.setdefault(prefix, set())
                if isinstance(type_set, set): type_set.add(t)

    def make_tool(self, name, env, viewport):
        return GToolGeneral(self.name_to_prefixes[name], env, viewport)

class GToolGeneral(GTool):

    def __init__(self, prefix_d, env, viewport):
        GTool.__init__(self, env, viewport)
        self.prefix_d = prefix_d

        # print self
        name = None
        ttypes = []
        for itype, tool in self.prefix_d.items():
            if isinstance(tool, Tool):
                name = tool.name
                otype = self.tools[name,itype].out_types
                output = ' '.join(type_to_c[t] for t in otype)
                args = ' '.join(type_to_c[t] for t in itype)
                ttypes.append("{} -> {}".format(args, output))
        print("Tool: {} : {}".format(name, ', or '.join(ttypes)))

    def update_basic(self, coor, args = (), types = ()):
        type_to_objlist = {
            Point : self.env.selectable_points,
            Line : self.env.selectable_lines,
            Circle : self.env.selectable_circles,
        }

        obj_lists = [type_to_objlist[t] for t in self.prefix_d[types]]
        obj,objn = self.coor_to_obj(coor, obj_lists)
        if obj is not None:
            args = args+(obj,)
            types = types+(type(objn),)
            tool = self.prefix_d[types]
            if isinstance(tool, Tool):
                self.confirm = self.run_tool, tool, args
            else: self.confirm_next = self.update_basic, args, types

        self.hl_select(*args)

    def run_tool(self, tool, args):
        step = ToolStep(tool, (), args)
        return self.env.add_step(step)
