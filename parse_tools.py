import geo_object as gt
import dim_tool as dim
from sparse_elim import SparseRow
import itertools
import primitive_pred as ppred
import primitive_constr as pcon
import logic_model as logic
from stop_watch import StopWatch, print_times
from tool_base import *

type_names = {
    'P' : gt.Point,
    'L' : gt.Line,
    'C' : gt.Circle,
    'D' : gt.Ratio,
    'A' : gt.Angle,
}
type_to_c = dict((t,c) for (c,t) in type_names.items())

class ParseError(Exception):
    def __str__(self):
        s = ', '.join(self.args)
        if hasattr(self, 'line') and hasattr(self, 'line_n'):
            s = "{}: {}\n  {}".format(self.line_n, self.line, s)
        return s

class CommandError(Exception):
    def __init__(self, c, msg):
        Exception.__init__(self, "{}: {}\n  {}".format(c.line_n, c.line, msg))

class Header:
    __slots__ = ['coexact', 'name', 'types']
    def __init__(self, line):
        if line.startswith('~'):
            self.coexact = True
            line = line[1:]
        else:
            self.coexact = False

        # (input, output, arg_permutations)

        name, types_str = line.split(':', 1)
        self.name = name.strip()
        if ' ' in self.name: raise ParseError()
        types_d = dict()
        def parse_subtypes(s):
            names = []
            types = []
            for t in s.split():
                if ':' in t:
                    name, t = t.split(':')
                    if name == '_': name = None
                else: name = None
                names.append(name)
                if t not in type_names: raise ParseError("unknown type '{}'".format(t))
                types.append(type_names[t])
            return tuple(types), tuple(names)
        for type_str in types_str.split(';'):
            if '->' in type_str:
                args, out = type_str.split('->')
            else: args, out = type_str, ''
            arg_types, arg_names = parse_subtypes(args)
            out_types, out_names = parse_subtypes(out)
            if arg_types in types_d:
                arg_names0, out_types0, out_names0, perms = types_d[arg_types]
                if out_types != out_types0: raise ParseError()
                if out_names != out_names0: raise ParseError()
                if len(set(arg_names)) != len(arg_names): raise ParseError()
                if len(set(arg_names0)) != len(arg_names0): raise ParseError()
                if len(arg_names0) != len(arg_names): raise ParseError()
                arg_to_pos = dict((name, i) for (i,name) in enumerate(arg_names0))
                perms.append(tuple(arg_to_pos[name] for name in arg_names))
            else: types_d[arg_types] = arg_names, out_types, out_names, []

        self.types = tuple(
            ((arg_types, arg_names), (out_types, out_names), tuple(perms))
            for arg_types, (arg_names, out_types, out_names, perms)
            in types_d.items()
        )

class Command:
    def __init__(self, line, line_n):
        self.line, self.line_n = line, line_n
        tokens = line.split()
        if '<-' in tokens:
            self.assumption = True
            i = tokens.index('<-')
        elif '=' in tokens:
            self.assumption = False
            i = tokens.index('=')
        else: raise ParseError("no '=' or '<-' in a line")

        self.output = tuple(
            (token if token != '_' else None)
            for token in tokens[:i]
        )
        tokens = tokens[i+1:]
        if '==' in tokens:
            if len(self.output) > 0: raise ParseError()
            i = tokens.index('==')
            lhs, rhs = tokens[:i], tokens[i+1:]
            ratio_exp = self.parse_ratio_expression(lhs, rhs)
            if ratio_exp is not None:
                self.t = 'equation'
                self.comp_t = gt.Ratio
                (var0,const0), (var1,const1) = ratio_exp
                self.equation_var = var0-var1
                self.equation_const = const0-const1
                return
            angle_exp = self.parse_angle_expression(lhs, rhs)
            if angle_exp is not None:
                self.t = 'equation'
                self.comp_t = gt.Angle
                (var0,const0), (var1,const1) = angle_exp
                self.equation_var = var0-var1
                self.equation_const = const0-const1
                return
            self.t = 'equality'
            [self.a] = lhs
            [self.b] = rhs
            return

        ratio_exp = self.parse_ratio_expression(tokens)
        if ratio_exp is not None:
            if len(self.output) != 1: raise ParseError()
            self.comp_t = gt.Ratio
            self.t = 'computation'
            (self.equation_var, self.equation_const), = ratio_exp
            return
        angle_exp = self.parse_angle_expression(tokens)
        if angle_exp is not None:
            if len(self.output) != 1: raise ParseError()
            self.comp_t = gt.Angle
            self.t = 'computation'
            (self.equation_var, self.equation_const), = angle_exp
            return
        self.t = 'standard'
        if len(tokens) == 0: raise ParseError("no command")
        self.name = tokens[0]
        self.args = tokens[1:]

    def to_eq_tool(self, var_to_index, angle_tool, ratio_tool):
        assert(self.t in ('equation', 'computation'))
        if self.comp_t == gt.Angle: pred = angle_tool
        elif self.comp_t == gt.Ratio: pred = ratio_tool
        else: raise Exception("Unexpected type for computation")
        var_str_coef = list(self.equation_var.items())
        var_ind_coef = []
        for vs, coef in var_str_coef:
            vi,t = var_to_index[vs]
            assert(t == self.comp_t)
            var_ind_coef.append((vi, coef))
        if len(var_ind_coef) == 0: variables, coefs = (),()
        else: variables, coefs = zip(*var_ind_coef)
        tool = pred(coefs, self.equation_const)
        return int(self.assumption), tool, variables, self
        
    def input_variables(self):
        if self.t == 'standard': return set(self.args)
        elif self.t == 'equality': return {self.a, self.b}
        else: return set(self.variables.keys())
        
    def parse_ratio_expression(self, *tokens_list):
        is_ratio = True
        for token in itertools.chain(*tokens_list):
            if token in ('*', '/'): break
            elif '^' in token and token.split('^',1)[1].isnumeric():
                break
            elif token.endswith('u') and token[:-1].isnumeric():
                break
        else: is_ratio = False

        if not is_ratio:
            for tokens in tokens_list:
                if len(tokens) == 1 and tokens[0].isnumeric():
                    is_ratio = True

        if not is_ratio: return None

        result = []
        for tokens in tokens_list:
            const = SparseRow(())
            variables = SparseRow(())
            state = 1
            for token in tokens:
                if token in ('*', '/'):
                    if state != 0: raise ParseError()
                    if token == '*': state = 1
                    else: state = -1
                else:
                    if state == 0: raise ParseError()
                    if '^' in token:
                        token, coef = token.split('^')
                        coef = int(coef)
                    else: coef = 1
                    coef *= state
                    if token.isnumeric():
                        const += dim.const_ratio(token)*coef
                    elif token.endswith('u') and token[:-1].isnumeric():
                        const += dim.const_ratio(token[:-1]) + dim.unit*coef
                    else:
                        variables += [(token, coef)]
                    state = 0
            if state != 0: raise ParseError()
            result.append((variables, const))

        return result

    def parse_angle_expression(self, *tokens_list):
        is_angle = True
        for token in itertools.chain(*tokens_list):
            if token in ('-', '+'): break
            elif token.isnumeric(): break
            elif token.endswith('^') and token[:-1].isnumeric():
                break
        else: is_angle = False

        if not is_angle: return None

        result = []
        for tokens in tokens_list:
            const = SparseRow(())
            variables = SparseRow(())
            coef = 1
            state = 'start'
            for i,token in enumerate(tokens):
                if token.isnumeric(): # multiplication coeficient
                    if state not in ('start', 'ang_start'): raise ParseError()
                    coef *= int(token)
                    state = 'ang_val'
                # degrees
                elif token.endswith('^') and token[:-1].isnumeric():
                    if state not in ('start', 'ang_start'): raise ParseError()
                    coef *= int(token[:-1])
                    const += dim.degree * coef
                    state = 'ang_end'
                elif token in ('+', '-'): # operation
                    if state not in ('start', 'ang_end'): raise ParseError()
                    if token == '-': coef = -1
                    else: coef = 1
                    state = 'ang_start'
                else: # angle variable
                    if state == 'ang_end': raise ParseError()
                    variables += [(token, coef)]
                    state = 'ang_end'
            if state != 'ang_end': raise ParseError()
            result.append((variables, const))
        return result

class ToolBox:
    def __init__(self):
        self.tool_dict = dict()
        self.eq_tool = EqualObjects()
        self.eq_tool.name = '=='
    def add_predicates(self, arg_types, out_types, steps, name, **kwargs):
        if name.startswith("small_angle"):
            fun_name = "small_angle"
            extra_args = int(name[len("small_angle"):]),
        else:
            fun_name = name
            extra_args = ()
        func = getattr(ppred, fun_name)
        return PrimitivePred(func, extra_args = extra_args)

    def add_predefined(self, arg_types, arg_names,
                       out_types, out_names, name, steps, **kwargs):
        func = getattr(pcon, name)
        raw_tool = PrimitiveConstr(func, out_types)
        raw_tool.name = name+"_raw"
        out_var_set = set(x for x in out_names if x is not None)
        self.var_to_index = dict(
            (v,(i,t))
            for (i,(v,t)) in enumerate(zip(arg_names, arg_types))
            if v is not None
        )
        self.next_index = len(arg_types)
        self.tool_steps = []
        out_indices = None
        def add_raw_step():
            nonlocal raw_tool, out_indices
            #print("Add raw step", name)
            self.tool_steps.append((0, raw_tool, tuple(range(len(arg_types))), None))
            self.var_to_index.update(
                (v,(i+self.next_index,t))
                for (i,(v,t)) in enumerate(zip(out_names, out_types))
                if v is not None
            )
            next_index2 = self.next_index+len(out_types)
            out_indices = tuple(range(self.next_index, next_index2))
            self.next_index = next_index2
            raw_tool = None
        for step in steps:
            if raw_tool is not None and len(step.input_variables() & out_var_set) > 0:
                add_raw_step()
            self.append_step(step)

        if raw_tool is not None: add_raw_step()
        return CompositeTool(self.tool_steps, len(arg_types), out_indices)

    def add_axioms(self, arg_types, arg_names, steps, **kwargs):
        self.var_to_index = dict(
            (v,(i,t))
            for (i,(v,t)) in enumerate(zip(arg_names, arg_types))
            if v is not None
        )
        self.next_index = len(arg_types)
        self.tool_steps = []
        for step in steps: self.append_step(step)
        return CompositeTool(self.tool_steps, len(arg_types), ())

    def add_constructed(self, arg_types, arg_names,
                        out_types, out_names, steps, check_validity, **kwargs):
        self.var_to_index = dict(
            (v,(i,t))
            for (i,(v,t)) in enumerate(zip(arg_names, arg_types))
            if v is not None
        )
        self.next_index = len(arg_types)
        self.tool_steps = []
        for step in steps: self.append_step(step)
        out_i = []
        for (v,t) in zip(out_names, out_types):
            i,t0 = self.var_to_index[v]
            assert(t == t0)
            out_i.append(i)
        tool = logic.compose_tool(self.tool_steps, arg_types, out_i, check_validity = check_validity)
        assert(tool is not None)
        return tool

    def append_step(self, step):
        strictness = int(step.assumption)
        if step.t == 'equality':
            va, ta = self.var_to_index[step.a]
            vb, tb = self.var_to_index[step.b]
            assert(type(ta) == type(tb))
            self.tool_steps.append((strictness, self.eq_tool, (va, vb), step))
        elif step.t == 'equation':
            self.tool_steps.append(
                step.to_eq_tool(self.var_to_index, dim.AnglePred, dim.RatioPred))
        elif step.t == 'computation':
            self.tool_steps.append(
                step.to_eq_tool(self.var_to_index, dim.AngleCompute, dim.RatioCompute))
            [out] = step.output
            if out is not None:
                assert(out not in self.var_to_index)
                self.var_to_index[out] = self.next_index, step.comp_t
            self.next_index += 1
        elif step.t == 'standard':
            if len(step.args) == 0: arg_i, arg_types = (), ()
            else:
                try:
                    arg_i, arg_types = zip(*[self.var_to_index[v] for v in step.args])
                except KeyError as e:
                    raise CommandError(
                        step,
                        "std command '{}': undefined variable {}".format(step.name, str(e)))
            key = step.name, arg_types
            if key not in self.tool_dict:
                arg_types_str = ' '.join(type_to_c[t] for t in arg_types)
                raise CommandError(step, "command '{} {}' not found".format(step.name, arg_types_str))
            tool, tool_out_types = self.tool_dict[key]
            if len(tool_out_types) != len(step.output):
                raise CommandError(step, "{} outputs expected, {} output given".format(
                    len(tool_out_types), len(step.output)))
            for i,(t,vs) in enumerate(zip(tool_out_types, step.output)):
                if vs is None: continue
                if vs in self.var_to_index:
                    raise CommandError(step, "double defined variable {}".format(vs))
                self.var_to_index[vs] = i+self.next_index,t
            self.tool_steps.append((strictness, tool, arg_i, step))
            self.next_index += len(tool_out_types)
        else: raise Exception('Unexpected command type')

    def add(self, mode, header, steps, check_validity):
        #print('--------------', header.name)
        add_fun = getattr(self, "add_"+mode)
        for (arg_types, arg_names), (out_types, out_names), perms in header.types:
            if len(out_types) > 0: assert(mode in ('predefined', 'constructed'))
            if len(steps) > 0: assert(mode != 'predicates')
            tool = add_fun(arg_types = arg_types, arg_names = arg_names,
                           out_types = out_types, out_names = out_names,
                           name = header.name, steps = steps,
                           check_validity = check_validity,
            )
            if header.coexact:
                assert(mode == 'predicates')
                tool.willingness = 1
            if len(perms) > 0:
                assert(mode in ('predicates', 'predefined'))
                tool.arg_permutations = perms
            key = header.name, arg_types
            assert(key not in self.tool_dict)
            self.tool_dict[key] = tool, out_types
            tool.name = header.name

    def load_file(self, fname, check_validity = True):
        mode = None
        header, steps = None, []
        with open(fname) as f:
            for n,line in enumerate(f):
                try:
                    line = line.strip()
                    if len(line) == 0 or line.startswith('#'): continue
                    if line.startswith('-') and line.endswith('-'): # mode switch
                        if header is not None:
                            self.add(mode, header, steps, check_validity)
                            header, steps = None, []
                        mode = line.strip('- ').lower()
                    elif ':' in line: # header
                        if header is not None:
                            self.add(mode, header, steps, check_validity)
                        header, steps = Header(line), []
                    else: # step
                        steps.append(Command(line, n+1))
                except ParseError as e:
                    e.line = line
                    e.line_n = n+1
                    #e.args = '{}: {}\n  '.format(n+1, line)+e.args
                    #print("Parse error on line {}: {}".format(n+1, line))
                    raise

if __name__ == "__main__":
    tools = ToolBox()
    with StopWatch('loading tools'):
        tools.load_file("tools2.txt")
    print_times()
