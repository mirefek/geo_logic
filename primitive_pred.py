from geo_object import *
import numpy as np

def not_eq(a, b):
    return a != b
def intersecting(cl1 : PointSet, cl2 : PointSet):
    if isinstance(cl1, Circle) and isinstance(cl2, Circle):
        dist = np.linalg.norm(cl1.c - cl2.c)
        return intersecting_cc(cl1, cl2)
    else:
        if isinstance(cl1, Circle): cl1, cl2 = cl2, cl1
        assert(isinstance(cl1, Line) and isinstance(cl2, Circle))
        return intersecting_lc(cl1, cl2)

def oriented_as(a1 : Point, b1 : Point, c1 : Point,
                a2 : Point, b2 : Point, c2 : Point):
    det1 = np.linalg.det(np.stack([b1.a-a1.a, c1.a-a1.a]))
    det2 = np.linalg.det(np.stack([b2.a-a2.a, c2.a-a2.a]))
    if eps_bigger(det1, 0) and eps_bigger(det2, 0): return True
    if eps_smaller(det1, 0) and eps_smaller(det2, 0): return True
    return False

def dim_less(d1 : Ratio, d2 : Ratio):
    return eps_smaller(d1.x, d2.x)

def not_on(p : Point, cl : PointSet):
    return not cl.contains(p.a)

def not_collinear(A : Point, B : Point, C : Point):
    return not eps_zero(np.linalg.det(np.stack([B.a-A.a, C.a-A.a])))

def lies_on(p : Point, cl : PointSet):
    return cl.contains(p.a)
