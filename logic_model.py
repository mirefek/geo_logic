import numpy as np
from geo_object import Angle, Ratio
from sparse_elim import SparseRow, EquationIndex, ElimMatrix, AngleChasing, equality_sr
from uf_dict import UnionFindDict
from fractions import Fraction

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

class EmptyTriggers():
    def run_triggers(self):
        pass
    def add(self, constr_id, args):
        pass
    def discard_node(self, x):
        return ()

class LogicModel():
    def __init__(self, triggers = None):
        self.obj_types = []
        self.num_model = []
        self.ratios = ElimMatrix()
        self.ratio_consts = dict()
        self.angles = AngleChasing()
        self.ufd = UnionFindDict()
        if triggers is not None:
            self.relstr = TriggerRelstr(triggers, self)
        else: self.relstr = EmptyTriggers()

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

    def check_equal(self, obj1, obj2):
        return self.ufd.is_equal(obj1, obj2)
    def get_constr(self, identifier, args):
        return self.ufd.get(identifier, args)
    def check_angle_equation(self, equation : SparseRow, frac_const : Fraction):
        return self.angles.query(equation, frac_const)
    def check_ratio_equation(self, equation : SparseRow, frac_const : Fraction):
        equation = self._make_ratio_equation(equation, frac_const, new_const = False)
        if equation is None: return False
        return bool(self.ratios.query(equation))

    def glue(self, obj1, obj2):
        if self.check_equal(obj1, obj2): return
        self._glue_reaction([(obj1, obj2)])
    def add_constr(self, identifier, args, vals):
        self.ufd.add(identifier, args, vals)
        self.relstr.add(identifier, args+vals)
        self.relstr.run_triggers()
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

    def _glue_reaction(self, to_glue_dict):
        to_glue_elim = []
        dnodes_moved = []
        while True:
            if to_glue_dict:
                a,b = to_glue_dict.pop()
                assert(self.obj_types[a] == self.obj_types[b])
                to_glue_elim.extend(self.ufd.glue(a, b))
            elif to_glue_elim:
                dnodes_moved.append(b)
                a,b = to_glue_elim.pop()
                na, nb = self.num_model[a], self.num_model[b]
                assert(na == nb)
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

        removed_edges = []
        for x in dnodes_moved:
            removed_edges.extend(self.relstr.discard_node(x))
        for label, nodes in removed_edges:
            nodes = self.ufd.tup_to_root(nodes)
            self.relstr.add(label, nodes)
        self.relstr.run_triggers()

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
