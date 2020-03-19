from collections import defaultdict
from stop_watch import StopWatch

"""
Alternative view to the lookup table, used by triggers.
It sees every value: (label, input) -> output
as a relation (label, data = input+output), and it allows to access
all such relations given label and a single element of data.
"""

class RelStr:
    def __init__(self):
        self.t_to_data = defaultdict(set)  # t -> set of tuples(x1,x2,...,xn)
        self.tobj_to_nb = defaultdict(set) # t,xi,i -> set of tuples(x1,x2,...,xn)
        self.obj_to_ti = defaultdict(set)   # xi -> set of pairs t,i

    def add_rel(self, t, data):
        if data in self.t_to_data[t]: return False
        self.t_to_data[t].add(data)
        for i,x in enumerate(data):
            self.tobj_to_nb[t,x,i].add(data)
            self.obj_to_ti[x].add((t,i))
        return True

    # removing a node (called upon gluing)
    def discard_node(self, obj, store_disc_edges = None):
        for t,i in self.obj_to_ti[obj]:
            edges = self.tobj_to_nb.pop((t,obj,i))
            self.t_to_data[t].difference_update(edges)
            for edge in edges:
                for i2,obj2 in enumerate(edge):
                    if obj2 != obj:
                        self.tobj_to_nb[t,obj2,i2].discard(edge)
            if store_disc_edges is not None:
                store_disc_edges.extend(
                    (t, data)
                    for data in edges
                )
        del self.obj_to_ti[obj]

    # debug function
    def check_consistency(self):
        test_tobj_to_nb = defaultdict(set)
        test_obj_to_ti = defaultdict(set)
        for t, edges in self.t_to_data.items():
            for edge in edges:
                for i,x in enumerate(edge):
                    test_obj_to_ti[x].add((t,i))
                    test_tobj_to_nb[t,x,i].add(edge)

        test_tobj_to_nb2 = dict(
            (key, s)
            for (key, s) in self.tobj_to_nb.items()
            if s
        )
        test_obj_to_ti2 = dict(
            (key, s)
            for (key, s) in self.obj_to_ti.items()
            if s
        )
        assert(test_tobj_to_nb == test_tobj_to_nb2)
        objs = set(test_obj_to_ti.keys()) | set(test_obj_to_ti2.keys())
        for obj in objs:
            s = test_obj_to_ti[obj]
            s2 = test_obj_to_ti2.get(obj, set())
            assert(s <= s2)

    # currently not used
    def copy(self):
        res = Relstr()
        res.t_to_data = self.t_to_data.copy()
        res.tobj_to_nb = self.tobj_to_nb.copy()
        res.obj_to_ti = self.obj_to_ti.copy()
        return res
