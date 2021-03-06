from primitive_tools import make_primitive_tool_dict
from fractions import Fraction
from geo_object import *
from tool_step import ToolStep, CompositeTool
from logical_core import LogicalCore

type_names = {
    'P' : Point,
    'L' : Line,
    'C' : Circle,
    'D' : Ratio,
    'A' : Angle,
}

type_to_c = dict(
    (t, c)
    for (c, t) in type_names.items()
)

class Parser:
    def __init__(self, tool_dict = None):
        if tool_dict is None: self.tool_dict = make_primitive_tool_dict()
        else: self.tool_dict = dict(tool_dict)
        self.variables = None # dict: name -> index, type
        self.var_num = None

    def add_var(self, name, t):
        if name in self.variables:
            raise Exception("Duplicate variable {} : {}, previous type {}".format(
                name, self.variables[name][1].__name__, t.__name__
            ))
        if name != '_': self.variables[name] = self.var_num, t
        self.var_num += 1

    def add_tool(self, name, tool):
        key = name, tool.arg_types
        if key in self.tool_dict:
            arg_types = ' '.join(x.__name__ for x in tool.arg_types)
            raise Exception("Duplicate tool {} : {}".format(
                name, tool
            ))
        self.tool_dict[key] = tool

    def var_index(self, name):
        return self.variables[name][0]
    def var_indices(self, names):
        return tuple(map(self.var_index, names))
    def var_type(self, name):
        return self.variables[name][1]

    # expect a tool step line (with "<-"), returns a ToolStep
    def parse_line(self, line_info, line):
        try:
            start_var_num = self.var_num
            tokens = line.split()
            debug_msg = "l{}: {}".format(*line_info)
            i = tokens.index('<-')
            outputs = tokens[:i]
            tool_name = tokens[i+1]
            args = iter(tokens[i+2:])
            hyper_params = []
            obj_args = []
            for arg in args:
                for hyper_type in (int, float, Fraction):
                    try:
                        val = hyper_type(arg)
                        hyper_params.append(val)
                        break
                    except ValueError:
                        pass
                else:
                    obj_args.append(arg)

            in_types = [
                type(x)
                for x in hyper_params
            ]
            in_types.extend(
                self.var_type(x)
                for x in obj_args
            )
            in_types = tuple(in_types)
            tool = self.tool_dict.get((tool_name, in_types), None)
            if tool is None:
                tool = self.tool_dict.get((tool_name, None), None)
                if tool is None:
                    raise Exception(
                        "Unknown tool: {} : {}".format(
                            tool_name, ' '.join(x.__name__ for x in in_types))
                    )
            if len(tool.out_types) != len(outputs):
                raise(Exception("Numbers of outputs do not match: {} : {}".format(
                    ' '.join(outputs), ' '.join(x.__name__ for x in tool.out_types)
                )))
            for o,t in zip(outputs, tool.out_types):
                self.add_var(o, t)

            return ToolStep(
                tool, hyper_params, self.var_indices(obj_args),
                start_var_num, debug_msg,
            )
        except Exception:
            print(debug_msg)
            raise

    # header every line is in the form (debug_info, str)
    # header is a single line, others are lists of lines
    def parse_tool(self, header, assump, impl, proof):
        try:
            header_info, header = header

            if not self.allow_axioms and impl and proof is None:
                raise Exception("Axioms are not allowed here")

            ## Decode header
            
            name, *data = header.split()
            i = data.index('->')
            i_data = data[:i]
            o_data = data[i+1:]

            self.variables = dict()
            self.var_num = 0
            arg_types = []
            for x in i_data:
                v,t = x.split(':')
                t = type_names[t]
                self.add_var(v, t)
                arg_types.append(t)

            ## Process steps

            assump = [
                self.parse_line(*line)
                for line in assump
            ]
            # save variable environment after assumptions, will be used again for proof
            var_after_assump = dict(self.variables), self.var_num

            impl = [
                self.parse_line(*line)
                for line in impl
            ]

            result = []
            out_types = []
            for x in o_data:
                v,t = x.split(':')
                t = type_names[t]
                i,t2 = self.variables[v]
                if t != t2:
                    raise Exception("expected type of {}: {}, obtained {}".format(
                        v, t, t2
                    ))
                out_types.append(t)
                result.append(i)

            var_to_name = dict(
                (i, name)
                for (name, (i,t)) in self.variables.items()
            )

            # restore variable environment after assumptions
            self.variables, self.var_num = var_after_assump
            if proof is not None:
                proof = [
                    self.parse_line(*line)
                    for line in proof
                ]
            var_to_name_proof = dict(
                (i, name)
                for (name, (i,t)) in self.variables.items()
            )

            arg_types = tuple(arg_types)
            out_types = tuple(out_types)
            tool = CompositeTool(
                assump, impl, result, proof, arg_types, out_types, name,
                basic_tools = self.basic_tools,
            )
            tool.var_to_name = var_to_name
            tool.var_to_name_proof = var_to_name_proof
            self.add_tool(name, tool)

        except Exception:
            print("l{}: Tool: {}".format(*header_info))
            raise

    def parse_file(self, fname, axioms = True, basic_tools = None):
        self.allow_axioms = axioms
        self.basic_tools = basic_tools

        try:
            with open(fname) as f:
                mode = "init"
                for i,iline in enumerate(f):
                    line_info = i+1, iline.strip()
                    line = iline
                    if '#' in line: line = line[:line.index('#')]
                    line = line.strip()
                    if line == '': continue
                    elif line == "THEN":
                        if mode != 'assume':
                            raise Exception("l{}: unexpected THEN".format(i))
                        mode = 'postulate'
                    elif line == "PROOF":
                        if mode != 'postulate':
                            raise Exception("l{}: unexpected PROOF".format(i))
                        mode = 'proof'
                        proof = []
                    elif "<-" in line:
                        if mode == 'assume': assump.append((line_info, line))
                        elif mode == 'postulate': impl.append((line_info, line))
                        elif mode == 'proof': proof.append((line_info, line))
                        else: raise Exception("l{}: unexpected mode {} for a command: {}".format(
                                line_info[0], mode, line_info[1]
                        ))
                    else:
                        if mode != 'init': self.parse_tool(header, assump, impl, proof)
                        assump = []
                        impl = []
                        proof = None
                        header = line_info, line
                        mode = 'assume'
                if mode != 'init': self.parse_tool(header, assump, impl, proof)
        except Exception:
            print("file: {}".format(fname))
            raise


if __name__ == "__main__":
    parser = Parser()
    parser.parse_file("basic.gl")
    for key, value in parser.tool_dict.items():
        if isinstance(key, tuple):
            name, in_types = key
            in_types = ' '.join(x.__name__ for x in in_types)
        else:
            name, in_types = key, "???"
        out_types = ' '.join(x.__name__ for x in value.out_types)
        if out_types == '': out_types = '()'
        print("{} : {} -> {}".format(name, in_types, out_types))

    parser.parse_file("construction.gl")
    logic = LogicalCore()

    parser.tool_dict['line', (Point, Point)].add_symmetry((1,0))
    parser.tool_dict['midpoint', (Point, Point)].add_symmetry((1,0))
    parser.tool_dict['dist', (Point, Point)].add_symmetry((1,0))
    parser.tool_dict['intersection', (Line, Line)].add_symmetry((1,0))

    parser.tool_dict['_', ()].run((), (), logic, 1)
