import geo_object as gt
import numpy as np

def radius_of(c):
    return gt.Ratio((np.log(c.r), 1))
def center_of(c):
    return gt.Point(c.c)
def dist(a,b):
    assert((a.a != b.a).any())
    return gt.Ratio((np.log(np.linalg.norm(a.a - b.a)), 1))
def direction_of(l):
    result = gt.Angle(np.angle(complex(*l.n)))
    return result

def intersection(l1, l2):
    assert(isinstance(l1, gt.Line) and isinstance(l2, gt.Line))
    [p] = gt.intersection_ll(l1, l2)
    return gt.Point(p)
def intersection_remoter(cl1, cl2, p):
    intersections = [gt.Point(x) for x in gt.intersection(cl1, cl2)]
    assert(len(intersections) == 2)
    intersections.sort(key = lambda p: np.dot(p.a, [1.2, 3.4]))
    return max(intersections, key = lambda x: x.dist_from(p.a))
def intersection0(cl1, cl2):
    intersections = [gt.Point(x) for x in gt.intersection(cl1, cl2)]
    assert(len(intersections) == 2)
    intersections.sort(key = lambda p: np.dot(p.a, [1.2, 3.4]))
    return intersections[0]
def point_on(cl1):
    true_coor = ps.closest_on(np.zeros([2]))
    return gt.Point(true_coor)
def line(p1, p2):
    assert(isinstance(p1, gt.Point))
    assert(isinstance(p2, gt.Point))
    return gt.line_passing_points(p1, p2)
def circle(center, radius):
    assert(isinstance(center, gt.Point))
    assert(isinstance(radius, gt.Ratio))
    return gt.Circle(center.a, np.exp(radius.x))
def line_with_direction(p, d):
    assert(isinstance(d, gt.Angle))
    assert(isinstance(p, gt.Point))
    cplx = np.exp(d.data*1j)
    normal_vector = np.array((cplx.real, cplx.imag))
    c = np.dot(normal_vector, p.a)
    return gt.Line(normal_vector, c)
