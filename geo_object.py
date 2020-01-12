import numpy as np

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

def vector_perp_rot(vec):
    return np.array((vec[1], -vec[0]))

def line_passing_points(point1, point2):
    normal_vector = vector_perp_rot(point1.a - point2.a)
    c = np.dot(normal_vector, point1.a)
    return Line(normal_vector, c)

class GeoObject:
    def identical_to(self, x):
        if not type(self) == type(x): return False
        return eps_identical(x.data, self.data)
    def __eq__(self, other):
        return self.identical_to(other)

    def dist_from(self, np_point):
        raise Exception("Not implemented")
    def draw(self, cr, corners, scale):
        raise Exception("Not implemented")

class NumObject(GeoObject):
    def draw(self, *args):
        pass

class Angle(NumObject):
    def __init__(self, data):
        self.data = data
    def identical_to(self, other):
        return eps_identical((self.data - other.data + 1) % np.pi, 1)

class Ratio(NumObject):
    def __init__(self, data):
        self.x, self.dim = data
        self.data = np.array(data)
    def __plus__(self, other):
        return Ratio(self.data + other.data)

class Point(GeoObject):
    def __init__(self, coor):
        self.a = np.array(coor)
        self.data = self.a

    def dist_from(self, np_point):
        return np.linalg.norm(self.a - np_point)

    def draw(self, cr, corners, scale):
        #cr.arc(self.a[0], self.a[1], 10, 0, 2*np.pi)
        #cr.set_source_rgb(1,1,1)
        #cr.fill()
        cr.arc(self.a[0], self.a[1], 3/scale, 0, 2*np.pi)
        cr.set_source_rgb(0,0,0)
        cr.fill()

class PointSet(GeoObject):
    def contains(self, np_point):
        raise Exception("Not implemented")
    def closest_on(self, np_point):
        raise Exception("Not implemented")

class Circle(PointSet):
    def __init__(self, center, r):
        assert(r > 0)
        self.c = np.array(center)
        self.r = r
        self.r_squared = self.r**2
        self.data = np.concatenate([self.c, [r]])

    def dist_from(self, np_point):
        center_dist = np.linalg.norm(self.c - np_point)
        return abs(self.r-center_dist)

    def contains(self, np_point):
        return abs(np.linalg.norm(np_point-self.c)-self.r) < epsilon

    def closest_on(self, np_point):
        vec = np_point-self.c
        vec *= self.r/np.linalg.norm(vec)
        return self.c + vec

    def draw(self, cr, corners, scale):
        cr.arc(self.c[0], self.c[1], self.r, 0, 2*np.pi)
        cr.set_source_rgb(0,0,0)
        cr.set_line_width(1/scale)
        cr.stroke()

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

        #print("n={} c={}".format(self.n, self.c))

    def get_endpoints(self, corners):

        result = [None, None]
        boundaries = list(zip(*corners))
        if np.prod(self.n) > 0:
            #print('swap')
            boundaries[1] = boundaries[1][1], boundaries[1][0]

        for coor in (0,1):
            if self.n[1-coor] == 0: continue
            for i, bound in enumerate(boundaries[coor]):
                p = np.zeros([2])
                p[coor] = bound
                p[1-coor] = (self.c - bound*self.n[coor])/self.n[1-coor]
                #print(p)
                #print("({} - {}) * ({} - {} = {})".format(
                #    p[1-coor], boundaries[1-coor][0], p[1-coor], boundaries[1-coor][1],
                #    (p[1-coor] - boundaries[1-coor][0]) * (p[1-coor] - boundaries[1-coor][1]),
                #))
                if (p[1-coor] - boundaries[1-coor][0]) * (p[1-coor] - boundaries[1-coor][1]) <= 0:
                    result[i] = p

        if result[0] is None or result[1] is None: return None
        else: return result

    def dist_from(self, np_point):
        c2 = np.dot(self.n, np_point)
        return abs(c2-self.c)

    def contains(self, np_point):
        return abs(np.dot(np_point, self.n)-self.c) < epsilon

    def closest_on(self, np_point):
        c2 = np.dot(self.n, np_point)
        return np_point - (c2-self.c)*self.n

    def identical_to(self, x):
        if not type(self) == type(x): return False
        if eps_identical(x.data, self.data): return True
        if eps_identical(x.data, -self.data): return True
        return False

    def draw(self, cr, corners, scale):
        endpoints = self.get_endpoints(corners)
        if endpoints is None: return

        cr.move_to(*endpoints[0])
        cr.line_to(*endpoints[1])

        cr.set_source_rgb(0,0,0)
        cr.set_line_width(1/scale)
        cr.stroke()


def intersection_ll(line1, line2):

    matrix = np.stack((line1.n, line2.n))
    b = np.array((line1.c, line2.c))
    if abs(np.linalg.det(matrix)) < epsilon: return []
    return [np.linalg.solve(matrix, b)]

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
        return intersection_ll(point_set1, point_set2)
    elif isinstance(point_set1, Line) and isinstance(point_set2, Circle):
        return intersection_lc(point_set1, point_set2)
    elif isinstance(point_set1, Circle) and isinstance(point_set2, Line):
        return intersection_lc(point_set2, point_set1)
    elif isinstance(point_set1, Circle) and isinstance(point_set2, Circle):
        result = intersection_cc(point_set1, point_set2)
        return result
