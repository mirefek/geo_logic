import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk
import cairo
import numpy as np

epsilon = 0.00001
def eps_identical(npa1, npa2):
    return max(np.abs(npa1-npa2)) < epsilon

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

    def dist_from(self, np_point):
        raise Exception("Not implemented")
    def draw(self, cr, corners):
        raise Exception("Not implemented")

class GFact:
    def check(self):
        raise Exception("Not implemented")
    def draw(self, cr, corners):
        pass

class Point(GeoObject):
    def __init__(self, x, y):
        self.a = np.array([x,y])
        self.data = self.a

    def dist_from(self, np_point):
        return np.linalg.norm(self.a - np_point)

    def draw(self, cr, corners):
        cr.arc(self.a[0], self.a[1], 10, 0, 2*np.pi)
        cr.set_source_rgb(1,1,1)
        cr.fill()
        cr.arc(self.a[0], self.a[1], 3, 0, 2*np.pi)
        cr.set_source_rgb(0,0,0)
        cr.fill()

class PointSet(GeoObject):
    def contains(self, np_point):
        raise Exception("Not implemented")
    def closest_on(self, np_point):
        raise Exception("Not implemented")

class PointInSet(GFact):
    def __init__(self, p, s):
        assert(isinstance(p, Point) and isinstance(s, PointSet))
        self.objects = [p, s]
        self.p = p
        self.s = s

    def check(self):
        return self.s.contains(self.p.a)

    def draw(self, cr, corners):
        if isinstance(self.s, Line):
            #print("draw fact")
            cr.move_to(*(self.p.a + 11*self.s.v))
            cr.line_to(*(self.p.a - 11*self.s.v))

            cr.set_source_rgb(0,0,0)
            cr.set_line_width(1)
            cr.stroke()

        elif isinstance(self.s, Circle):
            endpoints = intersection_cc(Circle(self.p.a[0], self.p.a[1], 11), self.s)
            if len(endpoints) < 2: return
            point_angle, angle1, angle2 = [
                np.angle(complex(*(endpoint - self.s.c)))
                for endpoint in [self.p.a] + endpoints
            ]
            #print(angle1, angle2)
            swap = (angle1 < point_angle) ^ (point_angle < angle2) ^ (angle2 < angle1)
            if swap:
                angle1, angle2 = angle2, angle1

            cr.arc(self.s.c[0], self.s.c[1], self.s.r, angle1, angle2)
            cr.set_source_rgb(0,0,0)
            cr.set_line_width(1)
            cr.stroke()

class Circle(PointSet):
    def __init__(self, x, y, r):
        assert(r > 0)
        self.c = np.array([x,y])
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

    def draw(self, cr, corners):
        cr.arc(self.c[0], self.c[1], self.r, 0, 2*np.pi)
        cr.set_source_rgb(0,0,0)
        cr.set_line_width(1)
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

    def draw(self, cr, corners):
        endpoints = self.get_endpoints(corners)
        if endpoints is None: return

        cr.move_to(*endpoints[0])
        cr.line_to(*endpoints[1])

        cr.set_source_rgb(0,0,0)
        cr.set_line_width(1)
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
    print("DET", det)
    if det < -epsilon: return []
    if det <= epsilon: return [center]
    center_deviation = np.sqrt(det)
    center_deviation = np.array(((center_deviation,),(-center_deviation,)))
    center_deviation = center_deviation * 0.5*vector_perp_rot(center_diff) / center_dist_squared

    return list(center + center_deviation)

def intersection(point_set1, point_set2):
    if isinstance(point_set1, Line) and isinstance(point_set2, Line):
        return intersection_ll(point_set1, point_set2)
    elif isinstance(point_set1, Line) and isinstance(point_set2, Circle):
        return intersection_lc(point_set1, point_set2)
    elif isinstance(point_set1, Circle) and isinstance(point_set2, Line):
        return intersection_lc(point_set2, point_set1)
    elif isinstance(point_set1, Circle) and isinstance(point_set2, Circle):
        result = intersection_cc(point_set1, point_set2)
        return result

class Drawing(Gtk.Window):

    def __init__(self):
        super(Drawing, self).__init__()    

        self.darea = Gtk.DrawingArea()
        self.darea.connect("draw", self.on_draw)
        self.darea.set_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.add(self.darea)

        self.darea.connect("button-press-event", self.on_button_press)
        self.connect("key-press-event", self.on_key_press)

        self.set_title("Drawing")
        self.resize(600, 400)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.connect("delete-event", Gtk.main_quit)
        self.show_all()

        self.objects = []
        self.facts = []
        self.tool = self.point_tool
        self.tool_data = []

    def on_draw(self, wid, cr):

        corners = [np.zeros([2]), np.array(self.get_size())]
        cr.rectangle(0, 0, corners[1][0], corners[1][1])
        cr.set_source_rgb(1, 1, 1)
        cr.fill()

        for obj in filter(lambda x: not isinstance(x, Point), self.objects):
            obj.draw(cr, corners)
        for obj in filter(lambda x: isinstance(x, Point), self.objects):
            obj.draw(cr, corners)
        for fact in self.facts:
            fact.draw(cr, corners)

    def on_key_press(self,w,e):

        keyval = e.keyval
        keyval_name = Gdk.keyval_name(keyval)
        #print(keyval_name)
        if keyval_name == 'p':
            self.tool = self.point_tool
            print("Point tool")
            self.tool_data = []
        elif keyval_name == 'l':
            self.tool = self.line_tool
            print("Line tool")
            self.tool_data = []
        elif keyval_name == 'c':
            self.tool = self.circle_tool
            print("Circle tool")
            self.tool_data = []
        elif keyval_name == 'd':
            self.tool = self.dep_point_tool
            print("Dependent point tool")
            self.tool_data = []
        elif keyval_name == 'i':
            self.tool = self.intersection_tool
            print("Intersection tool")
            self.tool_data = []
        elif keyval_name in ('Delete', 'KP_Delete'):
            self.tool = self.delete_tool
            print("Eraser tool")
            self.tool_data = []
        elif keyval_name == "Escape":
            Gtk.main_quit()
        else:
            return False

    def on_button_press(self, w, e):

        #if e.button != 1: return
        if e.type != Gdk.EventType.BUTTON_PRESS: return
        self.tool(e.x, e.y)
        self.darea.queue_draw()

    def remove_obj(self, obj):
        self.objects.remove(obj)
        # remove appropriate facts
        self.facts = [fact for fact in self.facts if obj not in fact.objects]

    def add_obj(self, obj):
        try:
            duplicity = next(o for o in self.objects if o.identical_to(obj))
            self.remove_obj(duplicity)
        except:
            pass
        self.objects.append(obj)

        print("{} objects".format(len(self.objects)))

    def add_fact(self, fact):
        self.facts.append(fact)

    def point_tool(self, x, y):
        self.add_obj(Point(x,y))

    def line_tool(self, x, y):
        dist, p = self.closest_point(x, y)
        if p is None: return
        if len(self.tool_data) == 0: self.tool_data.append(p)
        else:
            p0 = self.tool_data[0]
            if p0 != p:
                l = line_passing_points(p0, p)
                self.add_obj(l)
                self.add_fact(PointInSet(p0, l))
                self.add_fact(PointInSet(p, l))
            self.tool_data = []

    def circle_tool(self, x, y):
        dist, p = self.closest_point(x, y)
        if p is None: return
        if len(self.tool_data) == 1 and p == self.tool_data[0]: return

        self.tool_data.append(p)
        print("  {} points".format(len(self.tool_data)))
        if len(self.tool_data) == 3:
            a,b,c = self.tool_data
            r = np.linalg.norm(a.a-b.a)
            self.add_obj(Circle(c.a[0], c.a[1], r))
            self.tool_data = []
            #print("circle made")

    def intersection_tool(self, x, y):
        np_mouse = np.array([x,y])
        point_sets = [(point.dist_from(np_mouse), point)
            for point in self.objects if isinstance(point, PointSet)]
        if len(point_sets) < 2: return
        ps1 = min(point_sets, key = lambda x: x[0])
        point_sets.remove(ps1)
        ps2 = min(point_sets, key = lambda x: x[0])
        ps1 = ps1[1]
        ps2 = ps2[1]
        intersections = [Point(x[0], x[1]) for x in intersection(ps1, ps2)]
        if len(intersections) == 0:
            print("No intersection")
            return
        p = min(intersections, key = lambda x: x.dist_from(np_mouse))
        self.add_obj(p)
        self.add_fact(PointInSet(p, ps1))
        self.add_fact(PointInSet(p, ps2))

    def dep_point_tool(self, x, y):
        _,ps = self.closest_set(x, y)
        if ps is None: return
        np_point = ps.closest_on(np.array([x,y]))
        point = Point(np_point[0], np_point[1])
        self.add_obj(point)
        self.add_fact(PointInSet(point, ps))

    def delete_tool(self, x, y):
        pd, p = self.closest_point(x,y)
        sd, s = self.closest_set(x,y)

        if p is None and s is None: return
        if s is None: x=p
        elif p is None: x=s
        elif pd < 2*sd: x=p
        else: x=s

        self.remove_obj(x)

    def closest_obj(self, x, y, obj_type):
        np_mouse = np.array([x,y])
        points = [(point.dist_from(np_mouse), point)
            for point in self.objects if isinstance(point, obj_type)]
        if len(points) == 0: return 0, None
        return min(points, key = lambda x: x[0])

    def closest_point(self, x, y):
        return self.closest_obj(x, y, Point)

    def closest_set(self, x, y):
        return self.closest_obj(x, y, PointSet)

if __name__ == "__main__":
    win = Drawing()
    Gtk.main()
