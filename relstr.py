from collections import defaultdict
from stop_watch import StopWatch

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

    def copy(self):
        res = Relstr()
        res.t_to_data = self.t_to_data.copy()
        res.tobj_to_nb = self.tobj_to_nb.copy()
        res.obj_to_ti = self.obj_to_ti.copy()
        return res

class ExtensionGenerator:
    def __init__(self, ph):
        if not ph.active_edges:
            self.finished = True
            return

        def get_e_candidates(edge):
            t,x,i,xs = edge
            y = ph.x_dto_y[x]
            return edge, ph.codomain.tobj_to_nb[t,y,i]

        (m_t,m_x,m_i,m_xs), candidates = min(
            map(get_e_candidates, ph.active_edges),
            key = lambda ec: len(ec[1]),
        )
        #print("  "*len(ph.iter_stack), ph.x_dto_y)
        #print("  "*(1+len(ph.iter_stack)), m_t, m_x, m_i, m_xs)
        #print("  "*(1+len(ph.iter_stack)), candidates)

        if not candidates:
            self.finished = True
            return

        self.eq_check = []
        self.glue_check = []
        self.new_xs = []
        self.new_is = []
        new_is_d = dict()
        self.to_add_ys = []
        self.to_check = []
        for mi,x in enumerate(m_xs):
            if mi == m_i: continue
            if x in ph.x_dto_y:
                self.eq_check.append((mi, ph.x_dto_y[x]))
            elif x in new_is_d:
                self.glue_check.append((mi, new_is_d[x][0]))
            else:
                self.new_xs.append(x)
                new_is_d[x] = mi, len(self.new_is)
                self.new_is.append(mi)
                self.to_add_ys.append([])
                for t,xi in ph.domain.obj_to_ti[x]:
                    for data in ph.domain.tobj_to_nb[t,x,xi]:
                        if all(d in ph.x_dto_y or d in new_is_d for d in data):
                            l = [ph.x_dto_y.get(d, None) for d in data]
                            self.to_check.append((t,l))
                            for yi,d in enumerate(data):
                                new_i = new_is_d.get(d, None)
                                if new_i is not None:
                                    self.to_add_ys[new_i[1]].append((yi,l))

        self.cand_iter = iter(candidates)
        self.relstr = ph.codomain
        self.next_ext()

        #print("  "*(1+len(ph.iter_stack)), "recipe", self.new_is, self.new_xs)

    def next_ext(self):
        for ys in self.cand_iter:
            if any(ys[i] != y for (i,y) in self.eq_check): continue
            if any(ys[i] != ys[j] for (i,j) in self.glue_check): continue
            new_ys = [ys[i] for i in self.new_is]

            for y, to_add in zip(new_ys, self.to_add_ys):
                for i,l in to_add: l[i] = y
            if any(tuple(l) not in self.relstr.t_to_data[t]
                   for (t,l) in self.to_check): continue

            self.new_ys = new_ys
            self.finished = False
            return

        self.new_ys = None
        self.finished = True

class PartialHomo:
    def __init__(self, domain, codomain, xs, ys):
        self.domain = domain
        self.codomain = codomain
        self.x_to_y = list(zip(xs, ys))
        self.x_dto_y = dict(self.x_to_y)
        self.active_edges = set()
        for x in self.x_dto_y.keys():
            for (t,i) in self.domain.obj_to_ti[x]:
                self.active_edges.update(
                    (t,x,i,data)
                    for data in self.domain.tobj_to_nb[t,x,i]
                    if any(d not in self.x_dto_y for d in data)
                )
                #print(self.x_dto_y)
                #print(t,i, self.active_edges)
                #for data in self.domain.tobj_to_nb[t,x,i]:
                #    print("  ", data, [d not in self.x_dto_y for d in data])

        # history stack
        self.iter_stack = []
        self.x_to_y_lens = []
        self.active_edges_changes = []

    def extend(self, new_xs, new_ys):
        #print(new_xs, "->", new_ys)
        self.x_to_y_lens.append(len(self.x_to_y))
        self.x_to_y.extend(zip(new_xs, new_ys))
        self.x_dto_y.update(zip(new_xs, new_ys))
        added, removed = [], []
        for x in new_xs:
            for (t,i) in self.domain.obj_to_ti[x]:
                for data in self.domain.tobj_to_nb[t,x,i]:
                    edge = (t,x,i,data)
                    if any(d not in self.x_dto_y for d in data):
                        if edge not in self.active_edges:
                            self.active_edges.add(edge)
                            added.append(edge)
                    else:
                        for i2,x2 in enumerate(data):
                            redge = (t,x2,i2,data)
                            if redge in self.active_edges:
                                removed.append(redge)
                                self.active_edges.remove(redge)
        self.active_edges_changes.append((added, removed))

    def is_full(self):
        return not self.active_edges
    def go_back(self):
        l = self.x_to_y_lens.pop()
        for x,y in self.x_to_y[l:]: del self.x_dto_y[x]
        del self.x_to_y[l:]

        added, removed = self.active_edges_changes.pop()
        self.active_edges.difference_update(added)
        self.active_edges.update(removed)

    def search(self):
        self.iter_stack.append(ExtensionGenerator(self))
        while self.iter_stack[-1].finished:
            self.iter_stack.pop()
            if not self.iter_stack: return False
            self.go_back()

        cur = self.iter_stack[-1]
        self.extend(cur.new_xs, cur.new_ys)
        cur.next_ext()
        return True

    def run_trigger(self, cmd, to_run_list):
        with StopWatch('trigger {}'.format(cmd.__name__)):
            while True:
                if self.is_full():
                    to_run_list.append((cmd, dict(self.x_dto_y)))
                if not self.search(): return

class TriggerEnv:
    def __init__(self):
        self.t_trigger = defaultdict(list)

    def add(self, relstr, cmd):
        for t, data_s in relstr.t_to_data.items():
            l = self.t_trigger[t]
            for data in data_s:
                x_to_y = dict()
                eq_check = []
                for y,x in enumerate(data):
                    if x in x_to_y: eq_check.append(x_to_y[y], y)
                    else: x_to_y[x] = y
                rel_check = []
                for t2, data2_s in relstr.t_to_data.items():
                    for data2 in data2_s:
                        if t == t2 and data2 == data: continue
                        if all(x in x_to_y for x in data2):
                            rel_check.append((t2 , tuple(x_to_y[x] for x in data2)))

                xs,ys = zip(*x_to_y.items())
                l.append((eq_check, rel_check, xs, ys, relstr, cmd))

    def edge_added(self, relstr, t, data, to_run_list):
        for eq_check, rel_check, xs, ys, domain, cmd in self.t_trigger[t]:
            #print(t, data, eq_check, rel_check, xs, ys, domain)
            if any(data[i] != data[j] for (i,j) in eq_check): continue
            if any(
                tuple(map(lambda i: data[i], data2)) not in relstr.t_to_data[t2]
                for (t2,data2) in rel_check
            ): continue
            ys = tuple(data[i] for i in ys)
            part_homo = PartialHomo(domain, relstr, xs, ys)
            part_homo.run_trigger(cmd, to_run_list)

    def get_edge_labels(self):
        return set(self.t_trigger.keys())

class RelStrEnv:
    def __init__(self, triggers):
        self.relstr = RelStr()
        self.triggers = triggers
        self.edge_labels = triggers.get_edge_labels()
        self.to_run = []
        self.discarded = set()
        self.triggers_running = False

    def add(self, edge_label, data):
        if edge_label not in self.edge_labels: return
        if self.relstr.add_rel(edge_label, data):
            self.triggers.edge_added(self.relstr, edge_label, data, self.to_run)

    def run_triggers(self):
        if self.triggers_running: return
        self.triggers_running = True
        while self.to_run:
            action, x_to_y = self.to_run.pop()
            if any(y in self.discarded for y in x_to_y.values()): continue
            action(x_to_y)
        self.triggers_running = False

    def discard_node(self, n, store_disc_edges = None):
        self.discarded.add(n)
        self.relstr.discard_node(n, store_disc_edges)

    def glue_nodes(self, glue_dict):
        disc_edges = []
        for src in glue_dict.keys(): self.discard_node(src, disc_edges)
        for t,data in disc_edges:
            self.add(t, tuple(glue_dict.get(x, x) for x in data))
