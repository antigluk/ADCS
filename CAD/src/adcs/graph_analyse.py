
def _find_paths(matrix, start=0):
    to_visit = [(start, [])]
    while to_visit:
        curr, path = to_visit.pop()
        path.append(curr)
        adjs = [(index,path[:]) for (index,v) in enumerate(matrix[curr]) if v is not None]
        for adj,pth in adjs:
            if adj in path:
                yield path + [adj] # loop
            else:
                to_visit.append((adj,pth))
        if not adjs:
            yield path

def is_loop(path):
    return path[-1] in path[:-1]

def find_loops(matrix):
    g = _find_paths(matrix)
    return [path for path in g if is_loop(path)]

def find_paths(matrix):
    g = _find_paths(matrix)
    return [path for path in g if path[-1] not in path[:-1]]

def loop_from_looppath(loop_path):
    return loop_path[loop_path.index(loop_path[-1]):]

def _find_infinite_loops(matrix):
    loops_g = _find_paths(matrix)
    is_node = lambda k: len(filter(lambda x: x is not None, matrix[k])) <= 1
    for loop_path in loops_g:
        loop = loop_from_looppath(loop_path)
        if is_loop(loop_path) and all(map(is_node, loop)):
            yield loop

def find_infinite_loops(matrix):
    loops = _find_infinite_loops(matrix)
    return list(loops)