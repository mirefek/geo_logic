import geo_object
from geo_object import *
import itertools

def find_duplicities(objs, epsilon = geo_object.epsilon):
    glued_to = dict()
    d = dict()
    def add_to_dict(ident, t, data):
        idata = np.floor(data / epsilon).astype(int)
        for offset in itertools.product(*((0,1) for _ in idata)):
            d_index = idata + np.array(offset, dtype = int)
            d_index = tuple(d_index)
            ident2 = d.setdefault((t, d_index), ident)
            if ident != ident2:
                glued_to[ident].append(ident2)
                glued_to[ident2].append(ident)

    ident_list = list()
    for identifier, obj in objs:
        t = type(obj)
        ident_list.append(identifier)
        glued_to.setdefault(identifier, list())
        add_to_dict(identifier, t, obj.data)
        if t == Line: add_to_dict(identifier, t, -obj.data)

    for identifier in ident_list:
        if identifier not in glued_to: continue
        component = list()
        def find_component(x):
            x_objs = glued_to.pop(x, None)
            if x_objs is None: return
            component.append(x)
            for x2 in x_objs:
                find_component(x2)
        find_component(identifier)
        if component: yield component
