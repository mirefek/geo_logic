from math import gcd
from fractions import Fraction
from collections import defaultdict
from sparse_row import SparseRow
from stop_watch import StopWatch

def lcm(a, *args):
    for b in args:
        a *= b // gcd(a,b)
    return a

class EquationIndex:
    """
    EquationIndex is a helper identifier, any new equation obtains
    a new variable EquationIndex with coefficient 1.
    This allows tracing the origin of a derived equation, currently used
    for determining the common denominator
    = how much did we have to divide to obtain a derived equation
    """
    def __init__(self, equation):
        self.equation = equation

"""
ElimMatrix keeps a set of non-redundant linear equations (SparseRows).
User can add a new linear equation using function
  add(equation)
or check whether a certain equation can be derived from the equations added so far
using the function
  check(equation)
It also automatically detects if two variables are forced to be zero,
or proportional to each other, and communicates this fact back in the form of pairs
which are forced to be equal, returned by the "add" function.
Besides that, ElimMatrix also offer method
  get_inverse(x)
which finds a variable y (if possible) such that y == -x.

Variables which are non-zero, and not substituted by a proportion of other variable
are kept in a "matrix", rows of which are equations derived from the input equations.
Every row in the matrix must have a "pivot" variable such that there is no other
equation in the matrix containing this variable.
"""
class ElimMatrix:
    def __init__(self):
        self.rows = dict() # pivot -> row
        self.cols = defaultdict(set) # varname -> pivot set
        self.value_to_var = dict() # value_key -> pivot variable proportional to that
        self.zeroes = dict() # varname -> equation(size=1)
        self.proportional_to = dict() # varname -> (varname, equation(size=2) )
        self.root_to_proportions = dict() # varname -> size, dict(proportion -> varnames)

    def query(self, query_r):
        query_r = SparseRow(query_r)
        self._eliminate(query_r)
        if not all(isinstance(key, EquationIndex) for key in query_r.keys()):
            return 0
        return self._least_denom(query_r)

    def add(self, added):
        #assert(self.check_consistency())
        #print("elim.add({})".format(added))
        new_r = SparseRow(added)
        self._elim_by_proportions(new_r)
        eq_pure = [
            (x,coef) for (x,coef) in new_r.items()
            if not isinstance(x, EquationIndex)
        ]
        if len(eq_pure) <= 2 and any(x not in self.cols for x,coef in eq_pure):
            if not eq_pure: return False, () # Already known equation
            eqi = EquationIndex(added)
            new_r[eqi] = Fraction(1)
            to_glue_out = []
            if len(eq_pure) == 1:
                (x,coef), = eq_pure
                new_r *= -1/coef
                self._add_zero(x,new_r, to_glue_out)
            else:
                (x,cx),(y,cy) = eq_pure
                if x in self.cols or (y not in self.cols and
                                      self._get_root_to_prop(x)[0] > self._get_root_to_prop(y)[0]):
                    x,cx,y,cy = y,cy,x,cx
                new_r *= -1/cx
                self._add_proportion(x,y, new_r, to_glue_out)
            return True, to_glue_out

        self._elim_by_matrix(new_r)

        pivot_candidates = list(filter(
            lambda x: not isinstance(x, EquationIndex), new_r.keys(),
        ))
        if not pivot_candidates: return False, () # Already known equation

        # label equation
        eqi = EquationIndex(added)
        new_r[eqi] = Fraction(1)

        # select pivot
        if len(pivot_candidates) == 2:
            def cand_cost(cand):
                return 3*len(self.cols[cand]) + self._get_root_to_prop(cand)[0]
        else:
            def cand_cost(cand):
                return len(self.cols[cand])
        pivot = min(pivot_candidates, key = cand_cost)
        new_r *= -1 / new_r[pivot]

        to_glue_out = []
        cols_to_update = [
            (self.cols[x], x)
            for x in pivot_candidates
            if x != pivot
        ]
        #_, cols_to_update_proj2 = zip(*cols_to_update)
        #print("C", cols_to_update_proj2)

        # update matrix, compute glued
        main_col = set(self.cols[pivot])
        for ri in main_col:
            row = self.rows.get(ri)
            coef = row[pivot]
            self._deactivate_row(ri, row)

            row.iadd_coef(coef, new_r) # the essential command

            if self._activate_row(ri, row, to_glue_out):
                # kept in matrix
                for col, ci in cols_to_update:
                    if ci in row: col.add(ri)
                    else: col.discard(ri)
            else:
                # removed from matrix
                for col, ci in cols_to_update:
                    col.discard(ri)

        # add new row
        self.rows[pivot] = new_r
        if self._activate_row(pivot, new_r, to_glue_out):
            # add new row to columns
            self.cols[pivot] = { pivot }
            for col, ci in cols_to_update: col.add(pivot)

        return True, to_glue_out

    def get_inverse(self, x):
        r, eq_rx = self.proportional_to.get(x, (x, None))
        if eq_rx is None:
            ratio = Fraction(-1)
            denom_x = 1
        else:
            ratio = -eq_rx[r]
            denom_x = self._least_denom(eq_rx)            
        r_dict = self._get_root_to_prop(r)[1]
        y_list = r_dict.get(ratio, None)
        if y_list is None: return None, 0

        y = y_list[0]

        # get denominator
        _,eq_ry = self.proportional_to.get(y, (x, None))
        if eq_ry is None: denom_y = 1
        else: denom_y = self._least_denom(eq_ry)

        return y, lcm(denom_x, denom_y)

    # debug functions
    def print_self(self):
        keys = set(self.cols.keys())
        pivots = set(self.rows.keys())
        print("Pivots:", pivots)
        print("Variables:", keys)
        print("------------")
        keys = sorted(pivots)+sorted(keys-pivots)
        print(' '.join("{:^7}".format(k) for k in keys))
        for _,r in sorted(self.rows.items()):
            print(' '.join("{:>3}/{:<3}".format(
                r[k].numerator, r[k].denominator
            ) if r[k] != 0 else 7*' ' for k in keys))
        print(".....")
        for x,(y,eq) in self.proportional_to.items():
            print("  ({}) -> {}*({})".format(x, eq[y], y))
        for x in self.zeroes.keys():
            print("  ({}) -> 0".format(x))
        print("------------")

    def check_consistency(self): # debug function, verification of internal consistency
        ok = True
        for ri, r in self.rows.items():
            if r[ri] != -1:
                print("pivot {} has wrong coefficient in its row: {}".format(ri, r[ri]))
                ok = False
            for ci in r.keys():
                if isinstance(ci, EquationIndex): continue
                if ri not in self.cols[ci]:
                    print("[{}, {}] not in column".format(ri, ci))
                    ok = False
        for ci, col in self.cols.items():
            for ri in col:
                if ri not in self.rows or ci not in self.rows[ri]:
                    print("[{}, {}] not in row".format(ri, ci))
                    ok = False
        for x,eq in self.zeroes.items():
            if eq[x] != -1:
                print("zero {} has wrong coefficient: {}".format(ri, r[ri]))
                ok = False
            if any(y != x and not isinstance(y, EquationIndex) for y in eq.keys()):
                print("other variables in zero equation {}: {}".format(x, eq))
                ok = False
        for x,(y,eq) in self.proportional_to.items():
            if eq[x] != -1 or eq[y] == 0:
                print("proportion {} -> {} has wrong coefficients: {}".format(x,y, r))
                ok = False
            if any(z != x and z != y and not isinstance(z, EquationIndex) for z in eq.keys()):
                print("other variables in proportion equation {} -> {}: {}".format(x, y, eq))
                ok = False

        return ok

    # helper functions
    def _eliminate(self, row): # in place elimination of a single row
        self._elim_by_proportions(row)
        self._elim_by_matrix(row)

    def _elim_by_proportions(self, row):
        updates = []
        for var, coef in row.items():
            _,update = self.proportional_to.get(var, (None, None))
            if update is None: update = self.zeroes.get(var)
            if update is not None: updates.append((coef, update))
        for coef, update in updates:
            row += coef*update
    def _elim_by_matrix(self, row):
        updates = []
        for var, coef in row.items():
            update = self.rows.get(var)
            if update is not None: updates.append((coef, update))
        for coef, update in updates:
            row += coef*update        
            
    def _least_denom(self, row): # common denominator of the equation indices
        res = 1
        for key, coef in row.items():
            if not isinstance(key, EquationIndex): continue
            denom = coef.denominator
            res *= denom // gcd(res, denom)
        return res

    def _add_zero(self, x, eq, to_glue_out):
        if x in self.cols: del self.cols[x]
        if self.zeroes:
            y,eq2 = next(iter(self.zeroes.items()))
            denom = lcm(self._least_denom(eq),self._least_denom(eq2))
            to_glue_out.append((x,y, denom))
        self.zeroes[x] = eq
        if x in self.root_to_proportions:
            _, d = self.root_to_proportions[x]
            for q,l in d.items():
                for y in l:
                    if y != x:
                        eq2 = self.proportional_to[y][1] + q*eq
                        self.zeroes[y] = eq2
                        del self.proportional_to[y]
                        if q != 1:
                            denom = lcm(self._least_denom(eq),self._least_denom(eq2))
                            to_glue_out.append((x,y, denom))
            del self.root_to_proportions[x]

    def _get_root_to_prop(self, x):
        res = self.root_to_proportions.get(x, None)
        if res is None:
            res = 1, {Fraction(1) : [x]}
            self.root_to_proportions[x] = res
        return res

    def _add_proportion(self, x, y, eq_yx, to_glue_out):
        if x in self.cols: del self.cols[x]
        if 22 in eq_yx and 13 in eq_yx and 26 in eq_yx:
            raise Exception()
        # get data
        x_size, x_dict = self._get_root_to_prop(x)
        y_size, y_dict = self._get_root_to_prop(y)

        ratio_yx = eq_yx[y]
        denom_yx = self._least_denom(eq_yx)
        for ratio_xz, z_list in x_dict.items():
            ratio_yz = ratio_xz*ratio_yx

            # update proportional_to
            for z in z_list:
                if z == x: eq_yz = eq_yx
                else:
                    # x,eq2 ==
                    _,eq_xz = self.proportional_to[z]
                    # eq_yz = eq_xz + ratio_xz * eq_yx
                    eq_xz.iadd_coef(ratio_xz, eq_yx)
                    eq_yz = eq_xz
                self.proportional_to[z] = y, eq_yz

            # update y_dict
            zz_list = y_dict.setdefault(ratio_yz, z_list)
            if zz_list is not z_list:
                z = z_list[0]
                zz = zz_list[0]
                zz_list.extend(z_list)

                # get the denominator of the equation stating z == zz
                if z == x: denom_xz = 1
                else:
                    _, eq_xz = self.proportional_to[z]
                    denom_xz = self._least_denom(eq_xz)
                if zz == y: denom_yzz = 1
                else:
                    _, eq_yzz = self.proportional_to[zz]
                    denom_yzz = self._least_denom(eq_yzz)
                denom = lcm(denom_xz, denom_yzz, ratio_yz.denominator * denom_yx)

                # update to_glue
                to_glue_out.append((z, zz, denom))

        self.root_to_proportions[y] = x_size+y_size, y_dict
        del self.root_to_proportions[x]

    def _row_valkey(self, pivot, row):
        relevant_items = tuple(
            (x,coef) for (x,coef) in row.items()
            if not isinstance(x, EquationIndex) and x != pivot
        )
        if not relevant_items: return ()
        _,coef0 = min(relevant_items)
        return frozenset((x, coef/coef0) for (x,coef) in relevant_items)

    # remove from self.rows and self.cols
    def _remove_row(self, pivot, row):
        del self.rows[pivot]
        for x,coef in row.items():
            if not isinstance(x, EquationIndex) and x in self.cols:
                self.cols[x].discard(pivot)

    # updates only self.value_to_var, not self.rows nor self.cols
    def _deactivate_row(self, pivot, row):
        valkey = self._row_valkey(pivot, row)
        del self.value_to_var[valkey]

    def _activate_row(self, x, row, to_glue_out):
        valkey = self._row_valkey(x, row)
        if len(valkey) <= 1:
            if len(valkey) == 0:
                self._add_zero(x, row, to_glue_out)
            else:
                (y,_), = valkey
                self._add_proportion(x, y, row, to_glue_out)
            self._remove_row(x, row)
            return False
        else:
            y = self.value_to_var.setdefault(valkey, x)
            if y is x: return True

            # x and y are proportional

            # swap if more efficient
            cost_x, _ = self._get_root_to_prop(x)
            cost_y, _ = self._get_root_to_prop(y)
            if cost_x > cost_y:
                x,y = y,x
                eq_x = self.rows[x]
                eq_y = row
                self.value_to_var[valkey] = y
                preserve_x = True
            else:
                eq_x = row
                eq_y = self.rows[y]
                preserve_x = False

            # get equation stating x = coef*y
            z,_ = next(iter(valkey))
            eq = eq_x + eq_y * (-eq_x[z] / eq_y[z])

            # add as a proportion, remove from matrix
            self._add_proportion(x, y, eq, to_glue_out)
            self._remove_row(x, eq_x)

            return preserve_x

if __name__ == "__main__":

    elim = ElimMatrix()

    #elim.add(SparseRow({'A': Fraction(3, 2), 'B': Fraction(-1, 1)}))
    #elim.add(SparseRow({'C': Fraction(3, 2), 'D': Fraction(-1, 1)}))
    #elim.add(SparseRow({'A': Fraction(1, 1), 'C': Fraction(1, 1)}))
    #print(elim.get_inverse('D'))
    #print(elim.proportional_to)

    elim.add({0: Fraction(1, 1)})
    elim.add({0: Fraction(1, 1)})
    elim.add({3: Fraction(2, 1), 4: Fraction(-2, 1)})
    elim.add({6: Fraction(-1, 1), 4: Fraction(1, 1)})
    elim.add({6: Fraction(2, 1), 8: Fraction(-2, 1)})
    elim.add({3: Fraction(-1, 1), 8: Fraction(1, 1)})
    elim.add({3: Fraction(-1, 1), 10: Fraction(1, 1)})
    elim.add({13: Fraction(2, 1), 3: Fraction(-1, 1)})
    elim.add({13: Fraction(2, 1), 17: Fraction(-1, 1)})
    elim.add({3: Fraction(-1, 1), 17: Fraction(1, 1)})
    elim.add({12: Fraction(-1, 1), 18: Fraction(1, 1)})
    elim.add({13: Fraction(2, 1), 21: Fraction(-1, 1)})
    elim.add({3: Fraction(-1, 1), 21: Fraction(1, 1)})
    elim.add({12: Fraction(-1, 1), 22: Fraction(1, 1)})
    elim.add({25: Fraction(-1, 1), 26: Fraction(1, 1)})
    elim.add({27: Fraction(1, 1), 25: Fraction(-1, 1), 28: Fraction(-1, 1)})
    elim.add({28: Fraction(1, 1), 29: Fraction(-1, 1)})
    elim.add({28: Fraction(-1, 1), 29: Fraction(1, 1)})
    elim.add({30: Fraction(2, 1), 3: Fraction(-1, 1)})
    elim.add({30: Fraction(2, 1), 33: Fraction(-1, 1)})
    elim.add({3: Fraction(-1, 1), 33: Fraction(1, 1)})
    elim.add({12: Fraction(-1, 1), 34: Fraction(1, 1)})
    elim.add({12: Fraction(-1, 1), 25: Fraction(1, 1)})
    elim.add({3: Fraction(2, 1), 35: Fraction(-2, 1)})
    elim.add({6: Fraction(-1, 1), 35: Fraction(1, 1)})
    elim.add({6: Fraction(-1, 1), 37: Fraction(1, 1)})
    elim.add({43: Fraction(2, 1), 44: Fraction(-1, 1)})
    elim.add({45: Fraction(2, 1), 3: Fraction(-1, 1)})
    elim.add({30: Fraction(-1, 1), 45: Fraction(1, 1)})
    elim.add({43: Fraction(1, 1), 45: Fraction(1, 1), 46: Fraction(-1, 1)})
    elim.add({48: Fraction(-1, 1), 46: Fraction(1, 1)})
    elim.add({50: Fraction(2, 1), 51: Fraction(-1, 1)})
    elim.add({52: Fraction(2, 1), 3: Fraction(-1, 1)})
    elim.add({13: Fraction(-1, 1), 52: Fraction(1, 1)})
    elim.add({50: Fraction(1, 1), 52: Fraction(1, 1), 53: Fraction(-1, 1)})
    elim.add({55: Fraction(-1, 1), 53: Fraction(1, 1)})
    elim.add({44: Fraction(2, 1), 58: Fraction(-2, 1)})
    elim.add({60: Fraction(-1, 1), 58: Fraction(1, 1)})
    elim.add({51: Fraction(2, 1), 62: Fraction(-2, 1)})
    elim.add({64: Fraction(-1, 1), 62: Fraction(1, 1)})
    elim.add({66: Fraction(-1, 1), 68: Fraction(1, 1)})
    elim.add({70: Fraction(-1, 1), 72: Fraction(1, 1)})
    elim.add({6: Fraction(-1, 1), 80: Fraction(1, 1)})
    elim.add({6: Fraction(-1, 1), 83: Fraction(1, 1)})
    elim.add({44: Fraction(-1, 1), 48: Fraction(1, 1), 87: Fraction(-1, 1)})
    elim.add({48: Fraction(-1, 1), 3: Fraction(1, 1), 88: Fraction(-1, 1)})
    elim.add({87: Fraction(-1, 1), 88: Fraction(1, 1)})
    elim.add({70: Fraction(-1, 1), 89: Fraction(1, 1)})
    elim.add({51: Fraction(-1, 1), 55: Fraction(1, 1), 92: Fraction(-1, 1)})
    elim.add({55: Fraction(-1, 1), 3: Fraction(1, 1), 93: Fraction(-1, 1)})
    elim.add({92: Fraction(-1, 1), 93: Fraction(1, 1)})
    elim.add({66: Fraction(-1, 1), 94: Fraction(1, 1)})
    elim.add({100: Fraction(-1, 1), 101: Fraction(1, 1), 102: Fraction(-1, 1)})
    elim.add({103: Fraction(2, 1), 64: Fraction(-1, 1)})
    elim.add({105: Fraction(2, 1), 107: Fraction(-1, 1)})
    elim.add({103: Fraction(-1, 1), 105: Fraction(1, 1), 108: Fraction(-1, 1)})
    elim.add({102: Fraction(-1, 1), 108: Fraction(1, 1)})
    elim.add({110: Fraction(-1, 1), 111: Fraction(1, 1), 112: Fraction(-1, 1)})
    elim.add({113: Fraction(2, 1), 115: Fraction(-1, 1)})
    elim.add({116: Fraction(2, 1), 60: Fraction(-1, 1)})
    elim.add({113: Fraction(-1, 1), 116: Fraction(1, 1), 118: Fraction(-1, 1)})
    elim.add({112: Fraction(-1, 1), 118: Fraction(1, 1)})
    elim.add({70: Fraction(-1, 1), 119: Fraction(1, 1)})
    elim.add({66: Fraction(-1, 1), 120: Fraction(1, 1)})
    elim.add({115: Fraction(-1, 1), 77: Fraction(1, 1), 122: Fraction(-1, 1)})
    elim.add({77: Fraction(-1, 1), 60: Fraction(1, 1), 123: Fraction(-1, 1)})
    elim.add({122: Fraction(-1, 1), 123: Fraction(1, 1)})
    elim.add({0: Fraction(1, 1)})
    elim.add({64: Fraction(-1, 1), 77: Fraction(1, 1), 125: Fraction(-1, 1)})
    elim.add({77: Fraction(-1, 1), 107: Fraction(1, 1), 126: Fraction(-1, 1)})
    print('A')
    elim.check_consistency()
    print('B')
    elim.add({125: Fraction(-1, 1), 126: Fraction(1, 1)})
    print('C')
    elim.check_consistency()
