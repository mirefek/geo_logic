from geo_object import *
import numpy as np

def not_eq(a, b):
    return a != b
def intersecting(cl1, cl2):
    if isinstance(cl1, Circle) and isinstance(cl2, Circle):
        dist = np.linalg.norm(cl1.c - cl2.c)
        if eps_bigger(dist, cl1.r + cl2.r): return False
        if eps_bigger(cl1.r, dist + cl2.r): return False
        if eps_bigger(cl2.r, dist + cl1.r): return False
        return True
    else:
        if isinstance(cl1, Circle): cl1, cl2 = cl2, cl1
        assert(isinstance(cl1, Line) and isinstance(cl2, Circle))
        return eps_smaller(cl1.dist_from(cl2.c), cl2.r)

def oriented_as(a1, b1, c1, a2, b2, c2):
    det1 = np.linalg.det(np.stack([b1.a-a1.a, c1.a-a1.a]))
    det2 = np.linalg.det(np.stack([b2.a-a2.a, c2.a-a2.a]))
    if eps_bigger(det1, 0) and eps_bigger(det2, 0): return True
    if eps_smaller(det1, 0) and eps_smaller(det2, 0): return True
    return False

def small_angle(n, ang):
    if n == 1: return True
    x = (ang.data + np.pi/n) % np.pi
    return eps_bigger(x, 0) and eps_smaller(x, 2*np.pi/n)

def dim_less(d1, d2):
    return eps_smaller(d1.x, d2.x)

def not_on(p, cl):
    return not cl.contains(p.a)

def lies_on(p, cl):
    return cl.contains(p.a)
