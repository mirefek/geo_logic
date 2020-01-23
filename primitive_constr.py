from geo_object import *
import numpy as np

def radius_of(c : Circle) -> Ratio:
    return Ratio((np.log(c.r), 1))
def center_of(c : Circle) -> Point:
    return Point(c.c)
def dist(a : Point, b : Point) -> Ratio:
    assert((a.a != b.a).any())
    return Ratio((np.log(np.linalg.norm(a.a - b.a)), 1))
def direction_of(l : Line) -> Angle:
    ang = np.angle(complex(*l.n))/np.pi
    #print("direction_of: {} -> {}".format(l.n, ang))
    return Angle(ang)

def intersection(l1 : Line, l2 : Line) -> Point:
    assert(isinstance(l1, Line) and isinstance(l2, Line))
    return Point(intersection_ll(l1, l2))
def intersection_remoter(cl1 : PointSet, cl2 : PointSet, p : Point) -> Point:
    intersections = [Point(x) for x in intersection_univ(cl1, cl2)]
    assert(len(intersections) == 2)
    intersections.sort(key = lambda p: np.dot(p.a, [1.2, 3.4]))
    return max(intersections, key = lambda x: x.dist_from(p.a))
def intersection0(cl1 : PointSet, cl2 : PointSet) -> Point:
    intersections = [Point(x) for x in intersection_univ(cl1, cl2)]
    assert(len(intersections) == 2)
    intersections.sort(key = lambda p: np.dot(p.a, [1.2, 3.4]))
    return intersections[0]
def free_point(x : float, y : float) -> Point:
    return Point(np.array((x,y)))
def point_on(x : float, y : float, cl : PointSet) -> Point:
    true_coor = cl.closest_on(np.array((x,y)))
    return Point(true_coor)
def line(p1 : Point, p2 : Point) -> Line:
    assert(isinstance(p1, Point))
    assert(isinstance(p2, Point))
    return line_passing_points(p1, p2)
def circle(center : Point, radius : Ratio) -> Circle:
    assert(isinstance(center, Point))
    assert(isinstance(radius, Ratio))
    return Circle(center.a, np.exp(radius.x))
def line_with_direction(p : Point, d : Angle) -> Line:
    assert(isinstance(d, Angle))
    assert(isinstance(p, Point))
    cplx = np.exp(d.data*np.pi*1j)
    normal_vector = np.array((cplx.real, cplx.imag))
    c = np.dot(normal_vector, p.a)
    return Line(normal_vector, c)

def midpoint(A : Point, B : Point) -> Point:
    return Point((A.a + B.a)/2)
def half_direction(A : Point, B : Point) -> Angle:
    vec = vector_perp_rot(A.a - B.a)
    ang = np.angle(complex(*vec))/(2*np.pi)
    #print("half direction: {} -> {}".format(vec, ang))
    return Angle(ang)
def double_direction(A : Point, ang : Angle, d : Ratio) -> Point:
    cplx = -1j*np.exp(d.x + 2*np.pi*ang.data*1j)
    vector = np.array((cplx.real, cplx.imag))
    #print("double direction: {} -> {}".format(ang.data, vector))
    return Point(A.a + vector)

def circumcircle(A : Point, B : Point, C : Point) -> Circle:
    A,B,C = A.a, B.a, C.a
    bc = C-B
    ca = A-C
    ax_A = Line(bc, np.dot((B+C)/2, bc))
    ax_B = Line(ca, np.dot((C+A)/2, ca))
    center = intersection_ll(ax_A, ax_B)
    return Circle(center, np.linalg.norm(center-C))
