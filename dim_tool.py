from tool_base import Tool, ToolErrorNum, ToolErrorLog
from sparse_elim import SparseRow
from fractions import Fraction
from geo_object import Angle, Ratio
import numpy as np

def to_dim(v):
    return SparseRow([(v, 1)])
def to_fdim(v):
    return SparseRow([(v, Fraction(1,1))])
degree = to_dim(-1)
unit = to_fdim(-1)

def prime_decomposition(n):
    assert(n > 0)
    p2 = 0
    while n % 2 == 0:
        p2 += 1
        n /= 2
    if p2 > 0: result = [(2, p2)]
    else: result = []
    d = 3
    while d**2 <= n:
        if n % d == 0:
            p = 0
            while n % d == 0:
                p += 1
                n /= d
            result.append((d, p))
    if n > 1: result.append((n, 1))
    return result
def const_ratio(r, d = None):
    r = Fraction(r)
    if d is not None: r /= d
    assert(r > 0)
    sr = SparseRow((-d, p) for (d,p) in prime_decomposition(r.numerator))
    sr -= SparseRow((-d, p) for (d,p) in prime_decomposition(r.denominator))
    return sr

class DimTool(Tool):
    def __init__(self, coefs, const, willingness = 0):
        if isinstance(const, SparseRow): const = const.items()
        const = tuple(sorted(const))
        self.coefs = coefs
        self.const = const
        for x,n in const: assert(x < 0)
        self.identifier = (type(self), coefs, const)
        self.willingness = willingness
        self.init()

    def value(self, num_model, sr):
        if len(sr) == 0: return self.zero
        def to_num(x):
            if x >= 0:
                obj = num_model[x]
                assert(isinstance(obj, self.num_type))
                return obj.data
            else: return self.const_val(x)
        return self.num_type(sum(
            float(coef)*to_num(x) for (x,coef) in sr.items()
        ))

    def prepare_data(self, args, logic_model):
        assert(len(args) == len(self.coefs))
        sr = SparseRow(self.const)
        sr += (
            (arg, coef)
            for arg, coef in zip(args, self.coefs)
        )
        return sr, self.get_matrix(logic_model)
    
    def check_zero(self, args, logic_model, num_model, strictness):
        equation, matrix = self.prepare_data(args, logic_model)
        if num_model is not None:
            if self.value(num_model, equation) != self.zero:
                raise ToolErrorNum()
        if strictness <= self.willingness: # postulate
            logic_model.add_eq(matrix, equation)
        else: # check
            #matrix.print_self()
            #print(equation)
            #print(matrix.query(equation))
            if matrix.query(equation): return ()
            else: raise ToolErrorLog()

    def construct(self, args, logic_model, num_model, willingness):
        equation, matrix = self.prepare_data(args, logic_model)
        result = logic_model.new_object(self.num_type)
        logic_model.add_eq(matrix, equation - to_dim(result))

        if num_model is not None:
            num_model[result] = self.value(num_model, equation)
        return result,

class AngleTool(DimTool):
    def init(self):
        self.num_type = Angle
        self.zero = Angle(0)
    def const_val(self, v):
        assert(v == -1)
        return np.pi/180
    def get_matrix(self, logic_model):
        return logic_model.angles

class RatioTool(DimTool):
    def init(self):
        self.num_type = Ratio
        self.zero = Ratio((0,0))
    def const_val(self, v):
        assert(v < 0)
        if v == -1: np.array((np.log(50), 1))
        return np.array((np.log(-v), 0))
    def get_matrix(self, logic_model):
        return logic_model.ratios

class AnglePred(AngleTool):
    def run_no_cache(self, *all_args):
        self.check_zero(*all_args)
        return ()
class RatioPred(RatioTool):
    def run_no_cache(self, *all_args):
        self.check_zero(*all_args)
        return ()
class AngleCompute(AngleTool):
    def run_no_cache(self, *all_args):
        return self.construct(*all_args)
class RatioCompute(RatioTool):
    def run_no_cache(self, *all_args):
        return self.construct(*all_args)
