from geo_object import eps_smaller

def segment_union_diff(added_segments, subtracted_segments):
    segments = sorted([
        sorted([a,b])+[True] for (a,b) in added_segments
    ] + [
        sorted([a,b])+[False] for (a,b) in subtracted_segments
    ])
    result = []
    cur_a, cur_b = None, None
    erased = None
    for a,b,added in segments:
        if erased: a = max(a, erased)
        if not eps_smaller(a, b): continue

        if cur_b is not None and eps_smaller(cur_b, a):
            result.append((cur_a, cur_b))
            cur_a, cur_b = None, None
        if added:
            if cur_a is None: cur_a, cur_b = a,b
            else: cur_b = max(cur_b, b)
        else:
            if cur_a is not None:
                if eps_smaller(cur_a, a): result.append((cur_a, a))
            if erased is None: erased = b
            else: erased = max(erased, b)
            if cur_a is not None:
                cur_a = max(erased, cur_a)
                if not eps_smaller(cur_a, cur_b):
                    cur_a, cur_b = None, None

    if cur_b is not None: result.append((cur_a, cur_b))
    return result

def labeled_segment_diff(labeled, subtracted):
    result = []
    sub_iter = iter(subtracted + [(None, None)])
    sub_a, sub_b = next(sub_iter)
    for a,b,label in labeled:
        while sub_a is not None and eps_smaller(sub_b, b):
            if eps_smaller(a, sub_a): result.append((a,sub_a,label))
            a = max(a,sub_b)
            sub_a, sub_b = next(sub_iter)
        if sub_b is not None: b = min(sub_a, b)
        if eps_smaller(a, b): result.append((a,b,label))
    return result

if __name__ == "__main__":
    print(segment_union_diff(
        [(1,10), (12,16), (14, 20)],
        [(-2,0), (13,20), (21,25)],
    ))

    print(labeled_segment_diff(
        [(0,10,'a'), (10,20,'b'), (20,30, 'c')],
        [(-2,-1), (3,5), (18,22)],
    ))
