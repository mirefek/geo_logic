from fractions import Fraction

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
def equality_sr(a, b):
    return SparseRow(((a, Fraction(-1)), (b, Fraction(1))))
