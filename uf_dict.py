from collections import defaultdict
from stop_watch import StopWatch

class UnionFindDict:
    def __init__(self):
        self.obj_to_keys = defaultdict(set)
        self.obj_to_root_d = dict()
        self.obj_to_children = defaultdict(set)
        self.data = dict()

    def obj_to_root(self, obj):
        return self.obj_to_root_d.get(obj, obj)
    def tup_to_root(self, tup):
        return tuple(map(self.obj_to_root, tup))

    def _data_add(self, label, args, vals):
        #print("_data_add", label, args, vals)
        key = label, args
        if key in self.data:
            if self.data[key] == vals: return
            raise KeyError("key {} is already in the uf_dictionary".format(key))
        self.data[key] = vals
        for obj in args + vals:
            #print("  obj_to_keys[{}] :".format(obj))
            #print("    {}".format(self.obj_to_keys[obj]))
            self.obj_to_keys[obj].add(key)
            #print("    {}".format(self.obj_to_keys[obj]))

    def _data_remove(self, label, args):
        #print("_data_remove", label, args)
        key = label, args
        vals = self.data[key]
        del self.data[key]
        for obj in args + vals:
            #print("  obj_to_keys[{}] :".format(obj))
            #print("    {}".format(self.obj_to_keys[obj]))
            self.obj_to_keys[obj].discard(key)
            #print("    {}".format(self.obj_to_keys[obj]))
        return vals

    def add(self, label, args, vals):
        #print('add', label, args, vals)
        args, vals = map(self.tup_to_root, (args, vals))
        self._data_add(label, args, vals)

    def is_equal(self, n1, n2):
        n1, n2 = map(self.obj_to_root, (n1, n2))
        return n1 == n2

    def glue(self, n1, n2):
        #print('glue', n1, n2)
        result = self.multi_glue((n1, n2))
        #n = self.obj_to_root(n1)
        #print('ROOT:', n, self.obj_to_children[n])
        return result

    def multi_glue(self, *pairs):
        with StopWatch('uf_dict glue'):
            changed = []
            to_glue = list(pairs)
            while to_glue:
                n1, n2 = to_glue.pop()
                n1, n2 = map(self.obj_to_root, (n1, n2))
                if n1 == n2: continue

                c1, c2 = [
                    len(self.obj_to_children[n]) + len(self.obj_to_keys[n])
                    for n in (n1, n2)
                ]
                if c1 < c2: n1, n2 = n2, n1

                changed.append((n1, n2))
                self.obj_to_root_d[n2] = n1
                children1 = self.obj_to_children[n1]
                children2 = self.obj_to_children[n2]
                for child in children2:
                    self.obj_to_root_d[child] = n1
                children1.update(children2)
                children1.add(n2)
                children2.clear()
                #print("{} : {}".format(n2, self.obj_to_keys[n2]))
                for key in tuple(self.obj_to_keys[n2]):
                    label, args = key
                    vals = self._data_remove(label, args)
                    args, vals = map(self.tup_to_root, (args, vals))
                    ori_val = self.get(label, args)
                    if ori_val is not None:
                        assert(len(vals) == len(ori_val))
                        to_glue.extend(zip(vals, ori_val))
                    else: self._data_add(label, args, vals)

            return changed

    def __contains__(self, key):
        return self.tup_to_root(key) in self.data

    def get(self, label, args): # default = None, otherwise tuple
        args = self.tup_to_root(args)
        return self.data.get((label, args), None)

if __name__ == "__main__":
    d = UnionFindDict()
    d.add("A", (1, 0), ())
    d.add("B", (1, 0), (2,))
    d.add("C", (1, 0), (2,))
    d.add("D", (1, 2), (3,))
    d.add("E", (3,), (4,))
    d.add("F", (3,), (4,))
    d.add("G", (3,), (5,))
    d.add("H", (3,), (5,))
    d.glue(1, 4)
    d.glue(2, 5)
    print(d.data)
