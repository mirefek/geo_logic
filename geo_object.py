import numpy as np

### approximal equality / inequalities
### inequality must hold by at least epsilon

epsilon = 0.00001
def eps_zero(npa):
    result = np.abs(npa) < epsilon
    if not isinstance(result, bool): result = result.all()
    return result
def eps_identical(npa1, npa2):
    return eps_zero(npa1-npa2)
def eps_smaller(x1, x2):
    return x1 + epsilon < x2
def eps_bigger(x1, x2):
    return eps_smaller(x2, x1)

### helper functions

def vector_perp_rot(vec): # rotate vector by 90 degrees
    return np.array((vec[1], -vec[0]))
def vector_direction(vec): # get direction of a vector in straight angle units
    return np.arctan2(vec[1], vec[0]) / np.pi
def vector_of_direction(direction, logsize = 0): # inverse to the former
    cplx = np.exp(logsize + np.pi*direction*1j)
    return np.array((cplx.real, cplx.imag))

class GeoObject:
    def identical_to(self, x): # check equality up to numerical inaccuracy
        if not type(self) == type(x): return False
        return eps_identical(x.data, self.data)
    def __eq__(self, other):
        return self.identical_to(other)

    # distance from a point in the form of a two-element numpy array
    def dist_from(self, np_point):
        raise Exception("Not implemented")

class NumObject(GeoObject): # angle or ratio
    pass

class Angle(NumObject):
    def __init__(self, data):
        self.data = data
    def __repr__(self):
        return "Angle({})".format(self.data)
    def identical_to(self, other):
        return eps_identical((self.data - other.data + 0.5) % 1, 0.5)

class Ratio(NumObject):
    # data = [x, dim], dim = 1 for a distance, dim = 0 for a distance ratio, etc.
    def __init__(self, data):
        self.x, self.dim = data
        self.data = np.array(data)
    def __repr__(self):
        return "Ratio({}):dim{}".format(np.exp(self.x), self.dim)
    def __plus__(self, other):
        return Ratio(self.data + other.data)

class Point(GeoObject):
    def __init__(self, coor):
        self.a = np.array(coor)
        self.data = self.a
    def __repr__(self):
        return "Point({}, {})".format(*self.data)

    def dist_from(self, np_point):
        return np.linalg.norm(self.a - np_point)

class PointSet(GeoObject): # line or circle
    # check whether a point (as np.array) is contained by the set up to numerical inaccuracy
    def contains(self, np_point):
        raise Exception("Not implemented")
    # returns closest point (as np.array) in the set to a given point (as np.array)
    def closest_on(self, np_point):
        raise Exception("Not implemented")

class Circle(PointSet):
    def __init__(self, center, r):
        assert(r > 0)
        self.c = np.array(center)
        self.r = r
        self.r_squared = self.r**2
        self.data = np.concatenate([self.c, [r]])
    def __repr__(self):
        return "Circle(center = {}, r = {})".format(self.c, self.r)

    def dist_from(self, np_point):
        center_dist = np.linalg.norm(self.c - np_point)
        return abs(self.r-center_dist)

    def contains(self, np_point):
        return abs(np.linalg.norm(np_point-self.c)-self.r) < epsilon

    def closest_on(self, np_point):
        vec = np_point-self.c
        vec *= self.r/np.linalg.norm(vec)
        return self.c + vec


class Line(PointSet):
    def __init__(self, normal_vector, c): # [x,y] in Line([a,b],c) <=> xa + yb == c
        assert((normal_vector != 0).any())
        normal_size = np.linalg.norm(normal_vector)
        normal_vector = normal_vector / normal_size
        c = c / normal_size
        self.n = normal_vector
        self.v = vector_perp_rot(normal_vector)
        self.c = c
        self.data = np.concatenate([normal_vector, [c]])

    def __repr__(self):
        return "Line(normal_vector = {}, c = {})".format(self.n, self.c)

    def dist_from(self, np_point):
        c2 = np.dot(self.n, np_point)
        return abs(c2-self.c)

    def contains(self, np_point):
        return abs(np.dot(np_point, self.n)-self.c) < epsilon

    def point_by_c(self, vc):
        return self.c * self.n + vc*self.v
    
    def closest_on(self, np_point):
        c2 = np.dot(self.n, np_point)
        return np_point - (c2-self.c)*self.n

    def identical_to(self, x):
        if not type(self) == type(x): return False
        if eps_identical(x.data, self.data): return True
        if eps_identical(x.data, -self.data): return True
        return False


### more helper constructions

def line_passing_np_points(np_point1, np_point2):
    normal_vector = vector_perp_rot(np_point1 - np_point2)
    c = np.dot(normal_vector, np_point1)
    return Line(normal_vector, c)
def line_passing_points(point1, point2):
    return line_passing_np_points(point1.a, point2.a)


"""
functions intersection_ll / _lc / _cc compute the intersection of
two point sets as a list (actually np.array) of size from 0 to 2,
of points (two-dimensional numpy arrays).
intersection_univ() then combines them together by detecting input types
"""

def intersection_ll(line1, line2):

    matrix = np.stack((line1.n, line2.n))
    b = np.array((line1.c, line2.c))
    if abs(np.linalg.det(matrix)) < epsilon: return None
    return np.linalg.solve(matrix, b)

def intersection_lc(line, circle):
    # shift circle to center
    y = line.c - np.dot(line.n, circle.c)
    x_squared = circle.r_squared - y**2
    if x_squared < -epsilon:
        #print("negative det")
        return []
    if x_squared <= epsilon: x = np.zeros((1,1))
    else:
        x = np.sqrt(x_squared)
        x = np.array(((x,),(-x,)))
    result = x*line.v + y*line.n
    # shift back
    return list(result + circle.c)

def intersection_cc(circle1, circle2):
    center_diff = circle2.c - circle1.c
    center_dist_squared = np.dot(center_diff, center_diff)
    center_dist = np.sqrt(center_dist_squared)
    if eps_zero(center_dist_squared): return []
    relative_center = (circle1.r_squared - circle2.r_squared) / center_dist_squared
    center = (circle1.c + circle2.c)/2 + relative_center*center_diff/2

    rad_sum  = circle1.r + circle2.r
    rad_diff = circle1.r - circle2.r
    det = (rad_sum**2 - center_dist_squared) * (center_dist_squared - rad_diff**2)
    if det < -epsilon: return []
    if det <= epsilon: return [center]
    center_deviation = np.sqrt(det)
    center_deviation = np.array(((center_deviation,),(-center_deviation,)))
    center_deviation = center_deviation * 0.5*vector_perp_rot(center_diff) / center_dist_squared

    return list(center + center_deviation)

def intersection_univ(point_set1, point_set2):
    if isinstance(point_set1, Line) and isinstance(point_set2, Line):
        return [intersection_ll(point_set1, point_set2)]
    elif isinstance(point_set1, Line) and isinstance(point_set2, Circle):
        return intersection_lc(point_set1, point_set2)
    elif isinstance(point_set1, Circle) and isinstance(point_set2, Line):
        return intersection_lc(point_set2, point_set1)
    elif isinstance(point_set1, Circle) and isinstance(point_set2, Circle):
        result = intersection_cc(point_set1, point_set2)
        return result

# numerical checks whether two point sets are intersecting in at least two points    
def intersecting_lc(l,c):
    return eps_smaller(l.dist_from(c.c), c.r)
def intersecting_cc(c1,c2):
    dist = np.linalg.norm(c1.c - c2.c)
    if not eps_smaller(dist, c1.r + c2.r): return False
    if not eps_smaller(c1.r, dist + c2.r): return False
    if not eps_smaller(c2.r, dist + c1.r): return False
    return True
