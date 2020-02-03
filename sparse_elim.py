from math import gcd, pi, floor
from fractions import Fraction
from collections import defaultdict
from stop_watch import StopWatch
from geo_object import eps_identical

class SparseRow(dict):
    def __init__(self, data):
        if isinstance(data, SparseRow):
            super(SparseRow, self).__init__(data)
        else:
            if isinstance(data, dict): data = data.items()
            super(SparseRow, self).__init__()
            self.__iadd__(data)
    def __getitem__(self, key):
        return self.get(key, 0)
    def __mul__(self, n):
        if n == 0: return zero_sr
        return SparseRow(
            (k, n*x) for (k,x) in self.items()
        )
    def __rmul__(self, n):
        return self.__mul__(n)
    def __imul__(self, n):
        if n == 0: self.clear()
        else:
            for k,x in self.items():
                self[k] = x*n
        return self

    def iadd_coef(self, coef, other):
        if coef == 0: return
        other = other.items()
        for k,x in other:
            if x == 0: continue
            x *= coef
            x2 = self.get(k, 0)+x
            if x2 == 0: del self[k]
            else: self[k] = x2
        return self
        
    def __iadd__(self, other):
        if isinstance(other, dict): other = other.items()
        for k,x in other:
            if x == 0: continue
            if not isinstance(x, Fraction): x = Fraction(x)
            x2 = self.get(k, 0)+x
            if x2 == 0: del self[k]
            else: self[k] = x2
        return self
    def __add__(self, other):
        res = SparseRow(self)
        res.__iadd__(other)
        return res
    def __isub__(self, other):
        self.__iadd__((k,-x) for (k,x) in other.items())
        return self
    def __sub__(self, other):
        res = SparseRow(self.items())
        res.__isub__(other)
        return res

zero_sr = SparseRow(())

def lcm(a,b):
    return a//gcd(a,b)*b
def equality_sr(a, b):
    return SparseRow(((a, Fraction(-1)), (b, Fraction(1))))

class EquationIndex:
    def __init__(self, equation):
        self.equation = equation

class ElimMatrix:
    def __init__(self):
        self.rows = dict() # pivot -> row
        self.cols = defaultdict(set) # varname -> pivot set
        self.value_to_var = dict() # tuple of (var, num) -> pivot variable equal to that

    def add(self, added):

        new_r = SparseRow(added)
        self.eliminate(new_r)
        pivot_candidates = list(filter(
            lambda x: not isinstance(x, EquationIndex), new_r,
        ))
        if not pivot_candidates: return False, () # Already known

        # label equation
        eqi = EquationIndex(added)
        new_r[eqi] = Fraction(1)

        # select pivot
        pivot = min(pivot_candidates, key = lambda x: len(self.cols[x]))
        new_r *= -1 / new_r[pivot]
        self.rows[pivot] = new_r

        glued = []
        self._row_updated_value(new_r, pivot, glued)

        cols_to_update = [
            (self.cols[x], x)
            for x in pivot_candidates
            if x != pivot
        ]

        # update matrix, compute glued
        for ri in self.cols[pivot]:
            row = self.rows[ri]
            coef = row[pivot]
            value = self._row_to_value(row, ri)
            if self.value_to_var[value] == ri:
                del self.value_to_var[value]

            row.iadd_coef(coef, new_r) # the essential command

            self._row_updated_value(row, ri, glued)
            for col, ci in cols_to_update:
                if ci in row: col.add(ri)
                else: col.discard(ri)

        self.cols[pivot] = { pivot }
        #self.cols[pivot] = None
        for col, ci in cols_to_update: col.add(pivot)

        return True, glued

    def query(self, query_r): # return 0 = not derivable, (d > 0) = odvoditelné pomocí dělení d
        query_r = SparseRow(query_r)
        self.eliminate(query_r)
        if not all(isinstance(key, EquationIndex) for key in query_r.keys()):
            return 0
        return self._least_denom(query_r)

    # helper functions
    def eliminate(self, row): # in place elimination of a single row
        updates = []
        for var, coef in row.items():
            update = self.rows.get(var)
            if update is not None: updates.append((coef, update))
        for coef, update in updates:
            row.iadd_coef(coef, update)

    def _least_denom(self, row): # common denominator of the equation indices
        res = 1
        for key, val in row.items():
            if not isinstance(key, EquationIndex): continue
            denom = val.denominator
            res = lcm(denom, res)
        return res

    def _row_to_value(self, row, pivot): # compute key for self.value_to_var
        return frozenset(
            (var, coef)
            for (var, coef) in row.items()
            if var != pivot and not isinstance(var, EquationIndex)
        )

    def _row_updated_value(self, row, ri, glued_list): # update value_to_var, or notice gluing
        value = self._row_to_value(row, ri)
        denom = self._least_denom(row)
        dest = ri,denom
        ri2,denom2 = self.value_to_var.setdefault(value, (ri,denom))
        if ri2 is not ri:
            glued_list.append((ri, ri2, lcm(denom, denom2)))

        if len(value) == 1:
            (var2, coef), = value
            if coef == 1: glued_list.append((ri, var2, denom))

    def check_cols(self): # debug function, verification of internal consistency
        ok = True
        for ri, r in self.rows.items():
            for ci in r.keys():
                if isinstance(ci, EquationIndex): continue
                if ri not in self.cols[ci]:
                    print("[{}, {}] not in column".format(ri, ci))
                    ok = False
        for ci, col in self.cols.items():
            for ri in col:
                if ci not in self.rows[ri]:
                    print("[{}, {}] not in row".format(ri, ci))
                    ok = False
        return ok

    def print_self(self):
        keys = set(self.cols.keys())
        pivots = set(self.rows.keys())
        print(pivots)
        print(keys)
        keys = sorted(pivots)+sorted(keys-pivots)
        print(' '.join("{:^7}".format(k) for k in keys))
        for _,r in sorted(self.rows.items()):
            print(' '.join("{:>3}/{:<3}".format(
                r[k].numerator, r[k].denominator
            ) if r[k] != 0 else 7*' ' for k in keys))

class AngleChasing:
    def __init__(self):
        self.elim = ElimMatrix()
        self.equal_to = dict() # var -> root, denominator
        self.root_to_vars = dict() # root -> size, dict( frac_diff -> var_list )
        self.value = dict() # var -> value

    def add_var(self, var, value):
        #print("    angles.add_var({}, {})".format(var, value))
        self.value[var] = value
        self.equal_to[var] = var, 1
        self.root_to_vars[var] = 1, { Fraction(0) : [var] }

    def query(self, equation, frac_offset):
        #print("    print(angles.query(SparseRow({}), Fraction({})))".format(
        #    equation, frac_offset
        #))
        denom = self.elim.query(equation)
        if denom == 0 or denom % frac_offset.denominator != 0: return False

        return self.num_check(equation, frac_offset)

    def num_check(self, equation, frac_offset):
        num_val = 0
        for v,coef in equation.items():
            if isinstance(v, EquationIndex): continue
            assert(coef.denominator == 1)
            num_val += self.value[v] * coef.numerator

        num_val += float(frac_offset)
        num_val = (num_val+0.5) % 1 - 0.5
        return eps_identical(num_val, 0)

    def has_exact_difference(self, a, b):
        return self.equal_to[a][0] == self.equal_to[b][0]

    def postulate(self, equation, frac_offset):
        #print("    angles.postulate(SparseRow({}), Fraction({}))".format(
        #    equation, frac_offset
        #))
        #assert(self.num_check(equation, frac_offset))
        denom = frac_offset.denominator
        if denom > 1: equation *= denom
        changed, to_glue = self.elim.add(equation)
        to_glue_out = []
        for x,y,denom in to_glue:
            #print("{} == {} (mod 1/{})".format(x,y,denom))
            x,denom2 = self.equal_to[x]
            denom = lcm(denom, denom2)
            y,denom2 = self.equal_to[y]
            denom = lcm(denom, denom2)
            if x == y: continue

            x_size, x_dict = self.root_to_vars[x]
            y_size, y_dict = self.root_to_vars[y]
            if y_size > x_size:
                x,y = y,x
                x_dict,y_dict = y_dict,x_dict
                x_size,y_size = y_size,x_size

            # find fractional difference between x,y

            numer_f = (self.value[y] - self.value[x]) * denom + 0.5
            numer = int(floor(numer_f)) % denom
            numer_f = numer_f % denom - 0.5
            assert(eps_identical(numer, numer_f))
            frac_dist = Fraction(numer, denom)

            # add y_dict to x_dict, calculate to_glue_out

            for fd2, y_var_list in y_dict.items():
                fd_sum = (fd2 + frac_dist)%1
                for y_var in y_var_list: self.equal_to[y_var] = x, fd_sum.denominator
                x_var_list = x_dict.setdefault(fd_sum, y_var_list)
                if x_var_list is not y_var_list:
                    to_glue_out.append((x_var_list[0], y_var_list[0]))
                    x_var_list.extend(y_var_list)

            del self.root_to_vars[y]
            self.root_to_vars[x] = (x_size + y_size), x_dict

        return to_glue_out

if __name__ == "__main__":

    angles = AngleChasing()

    angles.add_var(36, -1.5921653169057746)
    angles.add_var(39, -0.02136899011087801)
    angles.add_var(83, 1.5494273366840186)
    angles.add_var(86, 3.120223663478915)
    angles.add_var(89, -1.1510110184045386)
    angles.add_var(92, 0.419785308390358)
    angles.add_var(95, -2.7285459835681265)
    angles.add_var(133, 2.700438355088557)
    angles.add_var(168, 1.55616597505271)
    angles.add_var(172, 1.136380666662352)
    angles.add_var(173, -0.7165953582719934)
    angles.add_var(174, 1.1363806666623515)
    angles.add_var(201, -1.577534965163588)
    angles.add_var(206, 1.136380666662352)
    angles.add_var(210, -2.721807345199435)
    angles.add_var(211, 1.9838429968165634)
    angles.add_var(212, -4.705650342015998)
    angles.add_var(216, 4.2712346818834535)
    angles.add_var(218, 1.5494273366840186)
    angles.add_var(219, 4.2712346818834535)
    angles.add_var(228, 5.84203100867835)
    angles.add_var(232, -5.848769647047042)
    angles.add_var(233, -5.848769647047042)
    angles.add_var(239, 1.1363806666623517)
    angles.add_var(241, -0.021368990110935782)
    angles.add_var(242, -2.0052119869274994)
    angles.add_var(244, -4.2712346818834535)
    angles.add_var(272, 3.120223663478915)
    angles.add_var(274, 3.120223663478915)

    angles.postulate(SparseRow({83: Fraction(1, 1), 89: Fraction(-1, 1), 133: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({168: Fraction(1, 1), 92: Fraction(-1, 1), 172: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({92: Fraction(1, 1), 173: Fraction(-1, 1), 174: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({172: Fraction(-1, 1), 174: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({95: Fraction(1, 1), 89: Fraction(-1, 1), 201: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({36: Fraction(1, 1), 95: Fraction(-1, 1), 206: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({83: Fraction(-1, 1), 36: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({86: Fraction(-1, 1), 39: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({210: Fraction(1, 1), 211: Fraction(-1, 1), 212: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({218: Fraction(1, 1), 210: Fraction(-1, 1), 219: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({216: Fraction(-1, 1), 219: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({83: Fraction(-1, 1), 218: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({86: Fraction(1, 1), 210: Fraction(-1, 1), 228: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({95: Fraction(1, 1), 86: Fraction(-1, 1), 233: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({232: Fraction(-1, 1), 233: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({241: Fraction(1, 1), 211: Fraction(-1, 1), 242: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({239: Fraction(-1, 1), 242: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({86: Fraction(-1, 1), 241: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({89: Fraction(1, 1), 86: Fraction(-1, 1), 244: Fraction(-1, 1)}), Fraction(0))
    angles.postulate(SparseRow({83: Fraction(1, 1), 272: Fraction(-1, 1)}), Fraction(1/2))
    angles.postulate(SparseRow({86: Fraction(-1, 1), 272: Fraction(1, 1)}), Fraction(0))
    angles.postulate(SparseRow({86: Fraction(-1, 1), 274: Fraction(1, 1)}), Fraction(0))
