from collections import defaultdict

class UnionFindSet:
    def __init__(self):
        self.obj_to_rels = defaultdict(set)
        self.obj_to_root_d = dict()
        self.obj_to_children = defaultdict(set)
        self.data = set()

    def obj_to_root(self, obj):
        return self.obj_to_root_d.get(obj, obj)
    def tup_to_root(self, tup):
        return tuple(map(self.obj_to_root, tup))
    
    def add(self, tup):
        tup = self.tup_to_root(tup)
        for obj in tup:
            self.obj_to_rels[obj].add(tup)
        self.data.add(tup)

    def is_equal(self, n1, n2):
        n1, n2 = map(self.obj_to_root, (n1, n2))
        return n1 == n2

    def glue(self, n1, n2):
        n1, n2 = map(self.obj_to_root, (n1, n2))
        if n1 == n2: return False
        c1, c2 = [
            len(self.obj_to_children[n]) + len(self.obj_to_rels[n])
            for n in (n1, n2)
        ]
        if c1 > c2: n1, n2 = n2, n1
        self.obj_to_root_d[n2] = n1
        for child in self.obj_to_children[n2]: self.obj_to_root_d[child] = n1
        for tup in tuple(self.obj_to_rels[n2]): # copy the set to avoid undocumented behavior
            self.data.remove(tup)
            for obj in tup: self.obj_to_rels[obj].discard(tup)
            tup = self.tup_to_root(tup)
            for obj in tup: self.obj_to_rels[obj].add(tup)
            self.data.add(tup)

        return True

    def __contains__(self, tup):
        return self.tup_to_root(tup) in self.data
