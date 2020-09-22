import numpy as np
from geo_object import Angle, Ratio
from sparse_row import SparseRow, equality_sr
from sparse_elim import EquationIndex, ElimMatrix
from angle_chasing import AngleChasing
from uf_dict import UnionFindDict
from fractions import Fraction
from triggers import TriggerEnv, RelStrEnv
from stop_watch import StopWatch

# Returns list of pairs (prime, exponent), used for ratio equations
def prime_decomposition(n):
    assert(n > 0)
    p2 = 0
    while n % 2 == 0:
        p2 += 1
        n //= 2
    if p2 > 0: result = [(2, p2)]
    else: result = []
    d = 3
    while d**2 <= n:
        if n % d == 0:
            p = 0
            while n % d == 0:
                p += 1
                n //= d
            result.append((d, p))
    if n > 1: result.append((n, 1))
    return result


"""
A short notice on the format of (angle / ratio) equations:
Both equational types: angles and ratios contain an equation of the type
SparseRow (geometrical reference x_i -> int c_i)
and a fractional constant.
  Ratios: the general equation is of the form x_1^c_1 * x_2^c_2 * ...  * const = 1
  Angles: the general equation is of the form x_1*c_1 + x_2*c_2 + ...  + const = 0
"""

class LogicalCore():
    def __init__(self, basic_tools = None):
        self.obj_types = [] # array : geometrical reference -> type (Point, Line, ...)
        self.num_model = [] # array : geometrical reference -> numerical representation (object of the type)
        self.ratios = ElimMatrix() # known equation about distances / ratios
        self.ratio_consts = dict() # prime number -> reference to a ratio object representing it
        self.angles = AngleChasing() # known equation about angles
        self.ufd = UnionFindDict() # lookup table for memoized tools

        # for using triggers, we need to have access to the basic tools
        # if we don't have it, triggers are not applied (RelStrEnv is a dummy structure)
        if basic_tools is None: self.triggers = RelStrEnv(self)
        self.triggers = TriggerEnv(basic_tools, self)

        # zero angle
        self.exact_angle = self.add_obj(Angle(0))
        self.angles.postulate(SparseRow({self.exact_angle : 1}), Fraction(0))

    # given a numerical representation, create a new geometrical reference
    def add_obj(self, num_obj):
        index = len(self.num_model)
        self.num_model.append(num_obj)
        t = type(num_obj)
        self.obj_types.append(t)
        if t == Angle: self.angles.add_var(index, num_obj.data)
        #print("add {} : {}".format(index, t.__name__))
        return index

    def add_objs(self, num_objs):
        return tuple(self.add_obj(obj) for obj in num_objs)

    ### checking functions, they do not modify the logical core

    def check_equal(self, obj1, obj2): # equality
        return self.ufd.is_equal(obj1, obj2)
    def get_constr(self, identifier, args): # lookup table
        return self.ufd.get(identifier, args)
    def check_angle_equation(self, equation : SparseRow, frac_const : Fraction):
        return self.angles.query(equation, frac_const)
    def check_ratio_equation(self, equation : SparseRow, frac_const : Fraction):
        equation = self._make_ratio_equation(equation, frac_const, new_const = False)
        if equation is None: return False
        return bool(self.ratios.query(equation))

    ### postulating functions

    def glue(self, obj1, obj2): # equality
        if self.check_equal(obj1, obj2): return
        self._glue_reaction([(obj1, obj2)])
    def add_constr(self, identifier, args, vals): # lookup table
        args, vals = self.ufd.add(identifier, args, vals)
        self.triggers.add(identifier, args+vals)
        self.triggers.run()
    def add_angle_equation(self, equation : SparseRow, frac_const : Fraction):
        to_glue_dict = list(self.angles.postulate(equation, frac_const))
        self._glue_reaction(to_glue_dict)
    def add_ratio_equation(self, equation : SparseRow, frac_const : Fraction):
        equation = self._make_ratio_equation(equation, frac_const, new_const = True)
        to_glue_dict = [
            (a,b)
            for (a,b,d) in self.ratios.add(equation)[1]
        ]
        self._glue_reaction(to_glue_dict)

    ### helper functions

    """
    _glue_reaction expects a list of the form of pairs (a,b)
    where a,b are geometrical references proven to be equal.
    The list will be eventually made empty, while the functions
    traces extensionality and equality forced by
    the ratio and angle equations.
    """
    def _glue_reaction(self, to_glue_dict):
        to_glue_elim = []
        dnodes_moved = []
        while True:
            if to_glue_dict:
                a,b = to_glue_dict.pop()
                assert(self.obj_types[a] == self.obj_types[b])
                to_glue_elim.extend(self.ufd.glue(a, b))
            elif to_glue_elim:
                a,b = to_glue_elim.pop()
                dnodes_moved.append(b)
                na, nb = self.num_model[a], self.num_model[b]
                assert(na.identical_to(nb))
                t = type(na)
                if t == Ratio:
                    equation = equality_sr(a, b)
                    to_glue_dict.extend(
                        (a,b)
                        for (a,b,d) in self.ratios.add(equation)[1]
                    )
                elif t == Angle:
                    equation = equality_sr(a,b)
                    to_glue_dict.extend(
                        self.angles.postulate(equation, Fraction(0))
                    )
            else: break

        self.triggers.glue_nodes(dict(
            (x, self.ufd.obj_to_root(x))
            for x in dnodes_moved
        ))
        self.triggers.run()

    # embeds a fractional constant of an equation about ratios into the equation
    def _make_ratio_equation(self, equation, frac_const = 1, new_const = True):
        if frac_const == 1: return SparseRow(equation)
        primes = prime_decomposition(frac_const.numerator)
        primes.extend(
            (d,-p)
            for (d,p) in prime_decomposition(frac_const.denominator)
        )
        for d,_ in primes:
            if d not in self.ratio_consts:
                if new_const:
                    self.ratio_consts[d] = self.add_obj(Ratio((np.log(d), 0)))
                else: return None
        equation = equation + SparseRow(
            (self.ratio_consts[d], Fraction(p))
            for d,p in primes
        )
        return equation
