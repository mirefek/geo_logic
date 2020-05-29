from geo_object import *
import numpy as np

"""
This file contains annotated geometrical funtions.
They are loaded by primitive_tools.py, and converted into
tools of the names "prim__name", where "name" is the
original name in this file
"""

def radius_of(c : Circle) -> Ratio:
    return Ratio((np.log(c.r), 1))
def center_of(c : Circle) -> Point:
    return Point(c.c)
def dist(a : Point, b : Point) -> Ratio:
    assert((a.a != b.a).any())
    return Ratio((np.log(np.linalg.norm(a.a - b.a)), 1))
def direction_of(l : Line) -> Angle:
    return Angle(vector_direction(l.v))

def intersection(l1 : Line, l2 : Line) -> Point:
    assert(isinstance(l1, Line) and isinstance(l2, Line))
    return Point(intersection_ll(l1, l2))

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
    normal_vector = vector_of_direction(d.data+0.5)
    c = np.dot(normal_vector, p.a)
    return Line(normal_vector, c)

def midpoint(A : Point, B : Point) -> Point:
    return Point((A.a + B.a)/2)
def half_direction(A : Point, B : Point) -> Angle:
    return Angle(vector_direction(B.a - A.a)/2)
def double_direction(A : Point, ang : Angle, d : Ratio) -> Point:
    return Point(A.a + vector_of_direction(2*ang.data, d.x))

def circumcircle(A : Point, B : Point, C : Point) -> Circle:
    A,B,C = A.a, B.a, C.a
    bc = C-B
    ca = A-C
    ax_A = Line(bc, np.dot((B+C)/2, bc))
    ax_B = Line(ca, np.dot((C+A)/2, ca))
    center = intersection_ll(ax_A, ax_B)
    return Circle(center, np.linalg.norm(center-C))

def angle_2_to_3(ang2 : Angle) -> Angle:
    x = (ang2.data + 0.5) % 1 - 0.5
    return Angle(x*2 / 3)
