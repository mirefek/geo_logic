from geo_object import *
from parse import Parser
from movable_tools import add_movable_tools, MovableTool

# class for extracting some tools from the tool dictionary into a python object,
# also contains the original dictionary as "tool_dict" property
class ImportedTools:
    def __init__(self, tool_dict):
        # for triggers and movables
        self.lies_on_l = tool_dict['lies_on', (Point, Line)]
        self.lies_on_c = tool_dict['lies_on', (Point, Circle)]
        self.direction_of = tool_dict['direction_of', (Line,)]
        self.radius_of = tool_dict['radius_of', (Circle,)]
        self.center_of = tool_dict['center_of', (Circle,)]
        self.circle = tool_dict['circle', (Point, Ratio)]
        # for symmetries
        self.line = tool_dict[('line', (Point, Point))]
        self.dist = tool_dict[('dist', (Point, Point))]
        self.midpoint = tool_dict[('midpoint', (Point, Point))]
        self.intersection_ll = tool_dict[('intersection', (Line, Line))]

        # for GUI
        self.arc_length = tool_dict.get(('arc_length', (Point, Point, Circle)), None)
        self.angle_ll = tool_dict.get(('angle', (Line, Line)), None)
        self.angle_ppl = tool_dict.get(('angle', (Point, Point, Line)), None)
        self.angle_lpp = tool_dict.get(('angle', (Line, Point, Point)), None)
        self.angle_pppp = tool_dict.get(('angle', (Point, Point, Point, Point)), None)
        self.angle_tools = (
            self.angle_ll,
            self.angle_ppl,
            self.angle_lpp,
            self.angle_pppp,
        )
        self.is_tangent_cl = tool_dict.get(('is_tangent', (Circle, Line)), None)

        # special dictionary for movable tools
        self.tool_dict = dict(tool_dict)
        self.m = dict()
        for (name, arg_types), tool in tool_dict.items():
            if isinstance(tool, MovableTool):
                obj_types = tuple(x for x in arg_types if issubclass(x, GeoObject))
                out_type, = tool.out_types
                self.m[name, obj_types, out_type] = tool

    def __getitem__(self, key):
        return self.tool_dict[key]

# load basic.gl and the primitive tools around
def load_basic_tools(fname = "basic.gl"):
    parser = Parser()
    parser.parse_file(fname)
    tool_dict = parser.tool_dict
    basic_tools = ImportedTools(tool_dict)
    basic_tools.line.add_symmetry((1,0))
    basic_tools.dist.add_symmetry((1,0))
    basic_tools.intersection_ll.add_symmetry((1,0))
    basic_tools.midpoint.add_symmetry((1,0))
    add_movable_tools(tool_dict, basic_tools)
    return ImportedTools(tool_dict)

# load macros.gl
def load_tools(fname):
    basic_tools = load_basic_tools()
    parser = Parser(basic_tools.tool_dict)
    parser.parse_file(fname, axioms = False, basic_tools = basic_tools)
    return ImportedTools(parser.tool_dict)
