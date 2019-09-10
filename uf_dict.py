from collections import defaultdict
from stop_watch import StopWatch

class UnionFindDict:
    def __init__(self):
        self.obj_to_keys = defaultdict(set)
        self.obj_to_root_d = dict()
        self.obj_to_children = defaultdict(set)
        self.data = dict()

    def glueable(self, obj):
        return True
    def obj_to_root(self, obj):
        return self.obj_to_root_d.get(obj, obj)
    def tup_to_root(self, tup):
        return tuple(map(self.obj_to_root, tup))

    def data_add(self, key, val):
         if key in self.data:
             raise KeyError("key {} is already in the uf_dictionary".format(key))
         self.data[key] = val
         for obj in key + val:
             if self.glueable(obj):
                 self.obj_to_keys[obj].add(key)

    def data_remove(self, key, val):
        del self.data[key]
        for obj in key + val:
            if self.glueable(obj):
                self.obj_to_keys[obj].discard(key)

    def set(self, key, val = (), allow_glue = True):
        key, val = map(self.tup_to_root, (key, val))
        if allow_glue and key in self.data:
            if not allow_glue:
                raise Exception("cannot set {} to {} since it is already set to {}".format(
                    key, val, self.data[key]
                ));
            ori_val = self.data[key]
            assert(len(ori_val) == len(val))
            return self.multi_glue(*zip(ori_val, val))
        else:
            self.data_add(key, val)

    def is_equal(self, n1, n2):
        n1, n2 = map(self.obj_to_root, (n1, n2))
        return n1 == n2

    def glue(self, n1, n2):
        #print('glue', n1, n2)
        result = self.multi_glue((n1, n2))
        #n = self.obj_to_root(n1)
        #print('ROOT:', n, self.obj_to_children[n])

    def glue_hook(self, n1, n2, to_glue):
        pass

    def multi_glue(self, *pairs):
        with StopWatch('uf_dict glue'):
            changed = False
            to_glue = list(pairs)
            while len(to_glue) > 0:
                n1, n2 = to_glue.pop()
                if not self.glueable(n1) or not self.glueable(n2): continue
                n1, n2 = map(self.obj_to_root, (n1, n2))
                if n1 == n2: continue
                changed = True
                self.glue_hook(n1, n2, to_glue)

                c1, c2 = [
                    len(self.obj_to_children[n]) + len(self.obj_to_keys[n])
                    for n in (n1, n2)
                ]
                if c1 > c2: n1, n2 = n2, n1

                self.obj_to_root_d[n2] = n1
                children1 = self.obj_to_children[n1]
                children2 = self.obj_to_children[n2]
                for child in children2:
                    self.obj_to_root_d[child] = n1
                children1.update(children2)
                children1.add(n2)
                children2.clear()
                for key in tuple(self.obj_to_keys[n2]):
                    val = self.data[key]
                    self.data_remove(key, val)
                    key, val = map(self.tup_to_root, (key, val))
                    ori_val = self.get(key)
                    if ori_val is not None:
                        assert(len(val) == len(ori_val))
                        to_glue.extend(zip(val, ori_val))
                    else: self.data_add(key, val)

            return changed

    def __contains__(self, key):
        return self.tup_to_root(key) in self.data

    def get(self, key): # default = None, otherwise tuple
        return self.data.get(self.tup_to_root(key), None)

if __name__ == "__main__":
    d = UnionFindDict()
    d.set((1,2,3), (4,5,6))
    d.set((1,2,4), (4,5,1))
    print(d.data)
    print(d.glue(3,4))
    print(d.data)
    print(d.glue(1,2))
    print(d.glue(1,6))
    print(d.data)
