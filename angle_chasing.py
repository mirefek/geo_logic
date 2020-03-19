from sparse_row import SparseRow
from sparse_elim import ElimMatrix, lcm, EquationIndex
from math import floor
from fractions import Fraction
from geo_object import eps_identical

"""
AngleChasing is a superstructure of ElimMatrix in sparse_elim specifically
targeted to handling equations about angles.
Angles use the straight-angle units here, that is
  1/2 = 90 degrees, 1 = 180 degrees, 2 = 360 degrees, ...
Equations about angles are considered modulo 1 (modulo 180 degrees)
since the basic usage of an angle is a direction of a line, and a direction
of a line is unambiguous modulo 180 degrees only.

Since AngleChasing is using gaussian elimination (over a field)
taking equations modulo 1 is equivalent to taking equations modulo rationals.
Therefore, the logic checks only whether a certain equation is satisfied modulo
rational numbers, and the rest is checked numerically.

An equation is of the form
  x_1*c_1 + x_2*c_2 + ... + x_n*c_n + C = 0.
C is an extra constant called "frac_offset", and
the rest is encoded using a SparseRow.
"""

class AngleChasing:
    def __init__(self):
        self.elim = ElimMatrix()
        self.equal_to = dict() # var -> root, frac_dist
        self.root_to_vars = dict() # root -> size, dict( frac_diff -> var_list )
        self.value = dict() # var -> value

    # var is the variable (geometrical reference)
    # value is a numerical value (object of type Angle)
    def add_var(self, var, value):
        #print("    angles.add_var({}, {})".format(var, value))
        self.value[var] = value
        self.equal_to[var] = var, Fraction(0)
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

    def _get_frac_dist(self, f1, f2, denom):
        # find a fraction with denominator denom approximatelly equal to f2-f1
        numer_f = (f2 - f1) * denom + 0.5
        numer = int(floor(numer_f)) % denom
        numer_f = numer_f % denom - 0.5
        assert(eps_identical(numer, numer_f))
        return Fraction(numer, denom)

    def postulate(self, equation, frac_offset):
        #print("    angles.postulate(SparseRow({}), Fraction({}))".format(
        #    equation, frac_offset
        #))
        assert(self.num_check(equation, frac_offset))
        denom = frac_offset.denominator
        if denom > 1: equation *= denom
        changed, to_glue = self.elim.add(equation)
        to_glue_out = []
        for x,y,denom in to_glue:
            #print("{} == {} (mod 1/{})".format(x,y,denom))
            x,fd_x = self.equal_to[x]
            y,fd_y = self.equal_to[y]
            if x == y: continue
            denom = lcm(denom, (fd_x-fd_y).denominator)

            x_size, x_dict = self.root_to_vars[x]
            y_size, y_dict = self.root_to_vars[y]
            if y_size > x_size:
                x,y = y,x
                x_dict,y_dict = y_dict,x_dict
                x_size,y_size = y_size,x_size

            # find fractional difference between x,y

            frac_dist = self._get_frac_dist(self.value[y], self.value[x], denom)

            # add y_dict to x_dict, calculate to_glue_out

            for fd2, y_var_list in y_dict.items():
                fd_sum = (fd2 + frac_dist)%1
                for y_var in y_var_list: self.equal_to[y_var] = x, fd_sum
                x_var_list = x_dict.setdefault(fd_sum, y_var_list)
                if x_var_list is not y_var_list:
                    to_glue_out.append((x_var_list[0], y_var_list[0]))
                    x_var_list.extend(y_var_list)

            del self.root_to_vars[y]
            self.root_to_vars[x] = (x_size + y_size), x_dict

        return to_glue_out

    # find angle y such that it is proven that y == -x
    def get_complement(self, x):
        r, d_xr = self.equal_to[x]
        inv, denom = self.elim.get_inverse(r)
        if inv is None: return None
        d_ri = self._get_frac_dist(-self.value[r],self.value[inv], denom)
        y, d_iy = self.equal_to[inv]
        d_nxy = (-d_xr + d_ri + d_iy)%1
        #print("{} +{} -> {} inv[{}] -> {} +{} -> {}".format(x, d_xr, r, denom, inv, d_iy, y))
        nx_list = self.root_to_vars[y][1].get(d_nxy, ())
        if not nx_list: return None
        return nx_list[0]

if __name__ == "__main__":

    angles = AngleChasing()

    angles.add_var('X', 0.6)
    angles.add_var('A', 0.1)
    angles.postulate(SparseRow({'X': Fraction(1, 1), 'A': Fraction(-1, 1)}), Fraction(1,2))
    angles.add_var('B', 0.3)
    angles.postulate(SparseRow({'A': Fraction(1, 1), 'B': Fraction(-1, 1)}), Fraction(1,5))
    angles.add_var('Y', 0.4)
    angles.add_var('C', 0.9)
    angles.add_var('D', 0.7)
    angles.postulate(SparseRow({'Y': Fraction(1, 1), 'C': Fraction(-1, 1)}), Fraction(-1,2))
    angles.postulate(SparseRow({'C': Fraction(1, 1), 'D': Fraction(-1, 1)}), Fraction(-1,5))
    angles.postulate(SparseRow({'A': Fraction(1, 1), 'C': Fraction(1, 1)}), Fraction(0))
    print(angles.get_complement('B'))
    print(angles.equal_to)
