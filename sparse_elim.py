import numpy as np
from fractions import Fraction
from sortedcontainers import SortedSet
from collections import defaultdict
from stop_watch import StopWatch

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
        return SparseRow(
            (k, n*x) for (k,x) in self.items()
        )
    def __rmul__(self, n):
        return self.__mul__(n)
    def __imul__(self, n):
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

def egcd(a,b):
    A = np.array((a,1,0))
    B = np.array((b,0,1))
    while B[0] != 0:
        k = A[0] // B[0]
        A,B = B, A-k*B
    if A[0] > 0: A *= -1
    return A, B

class ElimMatrix:
    def __init__(self):
        self.rows = dict() # pivot -> row
        self.cols = defaultdict(set) # varname -> pivot set
        self.value_to_var = dict() # tuple of (var, num) -> pivot variable equal to that
    def glue(self, x, y):
        return self.add(((x, -1), (y, 1)))
    def is_equal(self, x, y):
        return self.query(((x, -1), (y, 1)))
    def sr_to_value(self, r):
        value = sorted(r.items(), reverse = True)
        if len(value) == 0 or value[0][1] != -1: return None
        else: return tuple(value[1:])
    def row_updated_value(self, ri, glued_list):
        value = self.sr_to_value(self.rows[ri])
        if value is None: return
        var = self.value_to_var.get(value, ri)
        if var is not ri: glued_list.append((ri, var))
        else: self.value_to_var[value] = ri
        if len(value) == 1:
            (var2, n), = value
            if n == 1: glued_list.append((ri, var2))

class ElimMatrixI(ElimMatrix):

    def add(self, new_r):
        with StopWatch("matrix elimination"):
            new_r = SparseRow(new_r)

            to_update = set()
            keys = SortedSet(new_r.keys())

            while len(keys) > 0:
                pivot = keys.pop()
                if pivot not in self.rows and (new_r is None or pivot not in new_r):
                    # no change of shape, only update cols[pivot]
                    col = self.cols[pivot]
                    col.difference_update(to_update)
                    for ri in to_update:
                        if pivot in self.rows[ri]: col.add(ri)
                    continue

                all_rows = False
                if pivot not in self.rows: # new_r is ready to add to the table
                    self.rows[pivot] = new_r
                    to_update.add(pivot)
                    if new_r[pivot] > 0: new_r *= -1
                    all_rows = True
                    pivot_r, new_r = new_r, None
                else:
                    pivot_r = self.rows[pivot]

                pivot_r_used = False
                def pivot_r_use():
                    nonlocal keys, pivot_r_used
                    if not pivot_r_used:
                        keys.update(pivot_r.keys())
                        keys.discard(pivot)
                        pivot_r_used = True

                pivot_x = pivot_r[pivot]
                if new_r is not None: # mixing pivot_r and new_r
                    new_x = new_r[pivot]
                    pivot_r_use()
                    if new_x % pivot_x == 0:
                        coef = new_x // pivot_x
                        new_r -= pivot_r * coef
                    else:
                        to_update.add(pivot)
                        self.value_to_var.pop(self.sr_to_value(pivot_r), None)
                        (pivot_x, c11, c12), (_, c21, c22) = egcd(pivot_x, new_x)
                        pivot_r, new_r = c11*pivot_r + c12*new_r, c21*pivot_r + c22*new_r
                        self.rows[pivot] = pivot_r
                        all_rows = True

                if all_rows: to_check = to_update | self.cols[pivot]
                else: to_check = to_update

                col = self.cols[pivot]
                col.difference_update(to_check)

                for ri in to_check:
                    if ri == pivot: continue
                    r = self.rows[ri]
                    x = r[pivot]
                    if x % pivot_x != 0:
                        col.add(ri)
                    coef = x // (-pivot_x)
                    if coef != 0:
                        pivot_r_use()
                        if all_rows:
                            to_update.add(ri)
                            self.value_to_var.pop(self.sr_to_value(r), None)
                        r += pivot_r * coef

            glued = []
            for ri in to_update:
                self.row_updated_value(ri, glued)

            return len(to_update) > 0, glued

    def query(self, query_r):
        query_r = SparseRow(query_r)

        keys = SortedSet(query_r.keys())
        while len(query_r) > 0:
            pivot = keys.pop()
            if pivot not in query_r: continue
            if pivot not in self.rows: return False
            pivot_r = self.rows[pivot]
            keys.update(pivot_r.keys())
            pivot_x = pivot_r[pivot]
            query_x = query_r[pivot]
            if query_x % pivot_x != 0: return False
            query_r -= pivot_r*(query_x // pivot_x)

        return True

    def check_cols(self):
        for ri, r in self.rows.items():
            if ri in self.cols[ri]:
                print("diagonal [{}, {}] in column".format(ri, ri))
            for ci in r.keys():
                if ri not in self.cols[ci] and ri != ci:
                    print("[{}, {}] not in column".format(ri, ci))
        for ci, col in self.cols.items():
            for ri in col:
                if ci not in self.rows[ri]:
                    print("[{}, {}] in column".format(ri, ci))

    def print_self(self):
        keys = sorted(self.cols.keys(), reverse = True)
        print(' '.join("{:^5}".format(k) for k in keys))
        for _,r in sorted(self.rows.items(), reverse = True):
            print(' '.join("{:^5}".format(r[k] if r[k] != 0 else '')
                           for k in keys))

class ElimMatrixF(ElimMatrix):

    def add(self, new_r):
        with StopWatch("matrix elimination"):
            if isinstance(new_r, dict): new_r = new_r.items()
            new_r = SparseRow((k, Fraction(x)) for (k,x) in new_r)
            keys = SortedSet(new_r.keys())
            new_r_pivot = None

            glued = []
            while len(keys) > 0:
                pivot = keys.pop()

                if pivot not in new_r: continue

                if pivot in self.rows:
                    pivot_r = self.rows[pivot]
                    keys.update(pivot_r.keys())
                    keys.discard(pivot)
                    #print('new_r += {} * {}'.format(pivot, new_r[pivot]))
                    new_r += pivot_r * new_r[pivot]
                    #print(new_r)

                elif new_r_pivot is None: # new_r is ready to add to the table
                    new_r *= -1/new_r[pivot]
                    to_update = set(self.cols[pivot])
                    for ri in to_update:
                        r = self.rows[ri]
                        self.value_to_var.pop(self.sr_to_value(r), None)
                        r += r[pivot] * new_r
                        self.row_updated_value(ri, glued)

                    # update self.cols -- modified rows
                    #print("{} x {}".format(set(new_r.keys()), to_update))
                    for ci in new_r.keys():
                        col = self.cols[ci]
                        col.difference_update(to_update)
                        for ri in to_update:
                            if ci in self.rows[ri]: col.add(ri)
                    new_r_pivot = pivot

                    self.rows[pivot] = new_r
                    continue

            # update self.cols -- added row
            if new_r_pivot:
                for ci in new_r.keys():
                    self.cols[ci].add(new_r_pivot)
                self.row_updated_value(new_r_pivot, glued)

            return new_r_pivot is not None, glued

    def query(self, query_r):
        if isinstance(query_r, dict): query_r = query_r.items()
        query_r = SparseRow((k, Fraction(x)) for (k,x) in query_r)
        query_r = SparseRow(query_r)

        keys = SortedSet(query_r.keys())
        while len(query_r) > 0:
            pivot = keys.pop()
            if pivot not in query_r: continue
            if pivot not in self.rows: return False
            pivot_r = self.rows[pivot]
            keys.update(pivot_r.keys())
            keys.remove(pivot)
            query_r += pivot_r * query_r[pivot]

        return True

    def check_cols(self):
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
            print(' '.join("{:>3}/{:<3}".format(r[k].numerator, r[k].denominator) if r[k] != 0 else 7*' '
                           for k in keys))

if __name__ == "__main__":
    m = ElimMatrixF()
    def add_and_print(**kwargs):
        print(m.add(kwargs.items()))
        m.print_self()
        m.check_cols()
        print('-'*40)
    #add_and_print(a = 2, c = 1, d = 1, e = 4, f = 2)
    add_and_print(a = 1, c = -1, d = 2)
    add_and_print(a = 1, c = -2, d = 1)
    add_and_print(a = 1, b = -1)
    #print(m.query((('a', 1), ('b', -1))))
    #add_and_print(a = 3, b = 1, d = 1, e = 6, f = 1)
    #add_and_print(a = 1, b = 2, c = 1)
    #print(m.query((('a', 1), ('b', 2), ('c', 1))))
