import numpy as np
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
            super(SparseRow, self).__init__((k,x) for (k,x) in data if x != 0)
    def __getitem__(self, key):
        return self.get(key, 0)
    def __mul__(self, n):
        if n == 0: return SparseRow()
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
    def __iadd__(self, other):
        if isinstance(other, dict): other = other.items()
        for k,x in other:
            if k in self:
                x2 = self[k]
                if x+x2 == 0: del self[k]
                else: self[k] = x+x2
            else: self[k] = x
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

def equality_sr(a, b):
    return SparseRow(((a, Fraction(-1)), (b, Fraction(1))))

class EquationIndex:
    def __init__(self, equation):
        self.equation = equation

class ElimMatrixF:
    def __init__(self):
        self.rows = dict() # pivot -> row
        self.cols = defaultdict(set) # varname -> pivot set
        self.value_to_var = dict() # tuple of (var, num) -> pivot variable equal to that

    def add(self, new_r):
        eqi = new_r
        new_r = SparseRow(new_r)
        self.eliminate(new_r)
        pivot_candidates = list(filter(
            new_r, lambda x: not isinstance(x, EquationIndex)
        ))
        if not pivot_candidates: return False, ()
        new_r[eq_i] = eqi
        pivot = min(pivot_candidates, key = lambda x: len(self.cols[x]))
        new_r *= -1 / new_r[pivot]
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
            if self.value_to_row[value] == ri:
                del self.value_to_row[value]

            row += (1/coef)*new_r # the essential command

            self._row_updated_value(row, ri, glued)
            for col, ci in cols_to_update:
                if ci in row: col.add(ri)
                else: col.discard(ri)

        return True, glued

    def query(self, query_r):
        query_r = SparseRow(query_r)
        self.eliminate(query_r)
        if not all(isinstance(key, EquationIndex) for key in query_r.keys())
            return 0
        return self._least_denom(query_r)

    # helper functions
    def eliminate(self, row): # in place elimination of a single row
        updates = []
        for var, coef in row.items():
            update = self.rows.get(var)
            if update is not None: updates.append(coef, update)
        for coef, update in updates:
            row += coef*update

    def _least_denom(self, row): # common denominator of the equation indices
        res = 1
        for key, val in row.items():
            if not isinstance(key, EquationIndex): continue
            denom = val.denominator
            res *= denom // np.gcd(res, denom)
        return res

    def _row_to_value(self, pivot, row): # compute key for self.value_to_var
        value = return [
            (var, coef)
            for (var, coef) in row.items()
            if var != pivot and not isinstance(var, EquationIndex)
        ]

    def _row_updated_value(self, row, ri, glued_list):
        value = self._row_to_value(row, ri)
        denom = _least_denom(row)
        v2,d2 = self.value_to_var.setdefault(value, (ri,denom))
        if v2 is not ri: glued_list.append((ri, var, denom * d2 / np.gcd(denom, d2)))

        if len(value) == 1:
            (var2, n), = value
            if n == 1: glued_list.append((ri, var2))

    def check_cols(self): # debug function, verification of internal consistency
        for ri, r in self.rows.items():
            for ci in r.keys():
                if ri not in self.cols[ci]:
                    print("[{}, {}] not in column".format(ri, ci))
        for ci, col in self.cols.items():
            for ri in col:
                if ci not in self.rows[ri]:
                    print("[{}, {}] not in row".format(ri, ci))

    def print_self(self):
        keys = sorted(self.cols.keys(), reverse = True)
        print(' '.join("{:^7}".format(k) for k in keys))
        for _,r in sorted(self.rows.items(), reverse = True):
            print(' '.join("{:>3}/{:<3}".format(
                r[k].numerator, r[k].denominator
            ) if r[k] != 0 else 7*' ' for k in keys))

class AngleChasing:
    def __init__(self):
        self.elim = ElimMatrixF()
        self.equal_to = dict() # var -> root
        self.root_to_vars = dict() # root -> size, dict( frac_diff -> var_list )
        self.values = dict() # var -> value

    def add_var(self, var, value):
        self.value[var] = value
        self.equal_to[var] = var
        self.root_to_vars = 1, { Fraction(0) : [var] }

    def query(self, equation, frac_offset):
        denom = self.elim.query(equation)
        if denom == 0 or denom % frac_offset.denominator != 0: return False

        return self.num_check(equation, frac_offset)

    def num_check(self, equation, frac_offset):
        num_val = 0
        for v,coef in equation.items():
            if isinstance(v, EquationIndex): continue
            assert(coef.denominator == 1)
            num_val += self.value[v] * coef.numerator

        num_val += float(frac_offset)*np.pi
        num_val = (num_val+1) % np.pi - 1
        return eps_identical(num_val, zero)

    def postulate(self, equation, frac_offset):
        assert(num_check(self, equation, frac_offset))
        equation = equation * frac_offset.denominator
        to_glue = self.elim.add(equation)
        to_glue_out = []
        for x,y,denom in to_glue:
            x = self.equal_to[x]
            y = self.equal_to[y]
            x_size, x_dict = self.root_to_vars[x]
            y_size, y_dict = self.root_to_vars[y]
            if y_size > x_size:
                x,y = y,x
                x_dict,y_dict = y_dict,x_dict
                x_size,y_size = y_size,x_size

            # find fractional difference between x,y

            numer_f = (self.value[y] - self.value[x]) / np.pi
            numer = int(np.floor(numer+0.5)) % denom
            assert(eps_identical(numer, numer_f))
            frac_dist = Fraction(numer, denom)

            # add y_dict to x_dict, calculate to_glue_out

            for fd2, y_var_list in y_dist.items():
                x_var_list = x_dict.setdefault(fd2 + frac_dist, y_var_list)
                if x_var_list is not y_var_list:
                    to_glue_out.append((x_var_list[0], y_var_list[0]))
                    x_var_list.extend(y_var_list)

            del self.root_to_vars[y]
            self.root_to_vars[x] = (x_size + y_size), x_dict

        return to_glue_out
