from time import time, gmtime, strftime
import sys

_d = dict()
_l = list()
_stack = ()

class StopWatch:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        global _stack
        self.ori_stack = _stack

        my_id = _stack+(self.name,)
        _stack = my_id

        global _d, _l

        self.last_time = time()
        if my_id not in _d:
            _d[my_id] = [0.0, 0]
            _l.append(my_id)
        self.el = _d[my_id]

    def __exit__(self, *exception_data): 

        duration = time() - self.last_time
        self.el[0] += duration
        self.el[1] += 1

        global _stack
        _stack = self.ori_stack


def seconds_to_readable(secs):
    ori_secs = secs
    secs = int(secs)
    minutes = secs // 60
    secs %= 60
    if not minutes: return "{:.3} sec".format(ori_secs)

    hours = minutes // 60
    minutes %= 60
    if not hours: return "{:02}:{:02}".format(minutes,secs)

    days = hours // 24
    hours %= 24
    result = ["{:02}:{:02}:{:02}".format(hours,minutes,secs)]

    weeks = days // 7
    days %= 7
    if days > 0:
        days_str = "{} day".format(days)
        if days > 1: days_str += "s"
        result.append(days_str)
    if weeks > 0:
        weeks_str = "{} week".format(weeks)
        if weeks > 1: weeks_str += "s"
        result.append(weeks_str)
    result.reverse()
    return ", ".join(result)

def print_times():
    if not _l: return

    scopes = {() : []}
    for scope in _l:
        scopes[scope[:-1]].append(scope[-1])
        scopes[scope] = []

    scope_list = []

    def process_scope(scope):
        if len(scope) > 0: scope_list.append(scope)
        for next_name in scopes[scope]:
            process_scope(scope+(next_name,))
    process_scope(())

    print("Time performance")
    for mode in scope_list:
        secs, enters = _d[mode]
        print("{}{}: {} = {} * {}".format(
            "  "*len(mode), mode[-1],
            seconds_to_readable(secs),
            enters, secs / enters,
        ))
    sys.stdout.flush()
