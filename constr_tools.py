import construction_v1 as ct
import geo_object as gt

predefined_d = {
    "center":               ct.ConstrCenter,
    "intersection":         ct.ConstrIntersectionUniq,
    "intersection1":        ct.ConstrIntersection0,
    "intersection2":        ct.ConstrIntersection1,
    "intersection_closer":  ct.ConstrIntersectionCloser,
    "intersection_remoter": ct.ConstrIntersectionRemoter,
    "line":                 ct.ConstrLine,
    "circle":               ct.ConstrCirc,
    "point_on":             ct.ConstrPointOnFixed,
}
type_d = {
    "P"  : gt.Point,
    "C"  : gt.Circle,
    "L"  : gt.Line,
    "CL" : gt.PointSet,
}
type_to_str_d = {
    gt.Point : 'P',
    gt.Line : 'L',
    gt.Circle : 'C',
    gt.PointSet : 'CL',
}
def t_to_s(x): return type_to_str_d[x]
def o_to_ts(x): return type_to_str_d[type(x)]

def parse_header(header):
    i = header.index(':')
    name = header[:i].strip()
    assert(' ' not in name)
    ftype = header[i+1:]
    i = ftype.index('->')
    arguments = ftype[:i].split()
    output = ftype[i+2:].split()
    def str_to_name_type(s):
        if ':' in s: name, t = s.split(':')
        else: name, t = '_', s
        return name, type_d[t]
    def str_to_name_type_l(l):
        return list(map(str_to_name_type, l))

    return name, str_to_name_type_l(arguments), str_to_name_type_l(output)

def parse_command(line):
    i = line.index('=')
    output = line[:i].split()
    command, *args = line[i+1:].split()
    return command, args, output

tool_dict = dict()

def find_tool(command, itypes, num_outputs = None):
    if command not in tool_dict:
        raise Exception("No tool of name '{}'".format(command))
    for tool in reversed(tool_dict[command]):
        if tool.can_apply(itypes, num_outputs): return tool
    raise Exception("No tool '{}' with arguments {} and {} outputs".format(command, itypes, num_outputs))

class ConstrTool:
    def __init__(self, name, idata, odata):
        global tool_dict
        if name not in tool_dict: tool_dict[name] = []
        tool_dict[name].append(self)
        self.name = name
        self.itypes = [t for n,t in idata]
        self.otypes = [t for n,t in odata]
    def can_apply(self, itypes, num_outputs = None, partial = False):
        if partial:
            if len(itypes) > len(self.itypes): return False
        else:
            if len(itypes) != len(self.itypes): return False
        for test_t, t in zip(itypes, self.itypes):
            if not issubclass(test_t, t): return False
        if num_outputs is not None and num_outputs != len(self.otypes): return False
        return True
    def apply(self, constr, input_data):
        output = self.run(constr, input_data)
        assert(len(output) == len(self.otypes))
        for obj, t in zip(output, self.otypes):
            assert(obj is None or isinstance(obj, t))
        return output
    def check(self):
        return True

class ElementaryTool(ConstrTool):
    def __init__(self, name, idata, odata):
        ConstrTool.__init__(self, name, idata, odata)
        assert(len(odata) == 1)
        self.constr_class = predefined_d[name]
    def run(self, constr, args):
        return (constr.add(self.constr_class, *args, force_add = True),)

class ComposedTool(ConstrTool):
    def __init__(self, name, idata, odata):
        ConstrTool.__init__(self, name, idata, odata)
        self.name = name
        self.input_names = [n for n,t in idata]
        self.output_names = [n for n,t in odata]
        self.available_names = dict(idata)
        self.commands = []

    def run(self, constr, args):
        obj_dict = dict(zip(self.input_names, args))
        for tool, in_names, out_names in self.commands:
            in_objs = [obj_dict[n] for n in in_names]
            out_objs = tool.apply(constr, in_objs)
            obj_dict.update(zip(out_names, out_objs))

        return [obj_dict[n] for n in self.output_names]

    def add_command(self, command, args, output):
        itypes = [self.available_names[arg] for arg in args]
        tool = find_tool(command, itypes, len(output))
        self.commands.append((tool, args, output))
        self.available_names.update(zip(output, tool.otypes))

    def check(self): # check if all output objects are constructed
        correct = True
        for n,t in zip(self.output_names, self.otypes):
            if n not in self.available_names:
                correct = False
                print("{} : {} of type {} not constructed".format(
                    self.name, n, t))
            elif not issubclass(self.available_names[n], t):
                correct = False
                print("{}, output {}: expected type {} constructed type {}".format(
                    self.name, n, t, self.available_names[n]))
        return correct

def parse_tools(fname):
    global tool_dict
    tool_dict = dict()
    mode = None
    last_tool = None
    with open(fname) as f:
        for i,line in enumerate(f):
            try:
                line = line.strip()
                if line == '': continue
                if line == "== PREDEFINED ==": mode = "predefined"
                elif line == "== CONSTRUCTED ==":
                    mode = "constructed"
                    last_tool = None
                else:
                    if '=' in line:
                        assert(mode == "constructed")
                        assert(last_tool is not None)
                        last_tool.add_command(*parse_command(line))
                    else:
                        assert(mode is not None)
                        header = parse_header(line)
                        if mode == "predefined":
                            ElementaryTool(*header)
                        else:
                            last_tool = ComposedTool(*header)
            except Exception:
                print("Line {}: {}".format(i+1, line))
                raise

    all_correct = True
    for tl in tool_dict.values():
        for tool in tl:
            all_correct = all_correct & tool.check()
    assert(all_correct)

if __name__ == "__main__":
    parse_tools('tools.txt')
