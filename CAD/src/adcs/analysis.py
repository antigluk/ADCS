from consts import *
from parse import parse
import graph_analyse

import warnings
from itertools import chain
from PyQt4 import QtCore
from operator import add

class LSAAlgorithmError(Exception):
    pass

class LSAAlgorithmWarning(Warning):
    pass

def assert_b(boolean, message="assertion failed"):
    if not boolean:
        print message
        raise LSAAlgorithmError(message)

def find_path(matrix, start, end, visited=None):
    " Is path from start to end exists in graph 'matrix'? "
    if visited is None: visited = []
    if start in visited:
        return False
    if start != end:
        targets = [i for i,v in enumerate(matrix[start]) if v is not None]
        return any([find_path(matrix, t, end, visited + [start]) for t in targets])
    else:
        return True



class LSAAnalyser(object):
    def __init__(self, parsed):
        self.parsed = parsed

    def signal_sanity_check(self, lst):
        indexes = {x.index for x in lst}
        if len(lst) == 0:
            return

        err = "indexes of %s signals should be consistent" % lst[0].name
        assert_b(min(indexes) == 1, err)
        assert_b(max(indexes) == len(indexes), err + " (some numbers missing)")

    def arrow_sanity_check(self, lst):
        indexes = {x.index for x in lst}
        if len(lst) == 0:
            return

        err = "indexes of %s arrows should be consistent" % ("UP" if lst[0].dir == ARROW_UP else "DOWN")
        assert_b(min(indexes) == 1, err)
        assert_b(max(indexes) == len(indexes), err + " (some numbers missing)")

    def _invert(self, signals):
        return [Signal(name=x.name, index=x.index, inverted=not x.inverted) for x in signals]
        # return not signals

    def _make(self, start, stack=None, full_stack=None, condition=True, condition_stack=None):
        if start >= len(self.enumerated): return
        if start == 0:
            print "============================="
            print "Make matrix"
            print "============================="
            self.connections = []
            self.connections_q = []
            self.y_matrix = [[[None,None] for y in self.barenodes] for x in self.in_signals]

        if not stack: stack = []
        if not full_stack: full_stack = []
        if not condition_stack: condition_stack = []

        curr = self.enumerated[start]
        if type(curr) is CertainNode:
            no_depth = False
            assert_b(not full_stack or type(full_stack[-1]) is not CertainNode or full_stack[-1].node.type != 'in',
                'Expected arrow after input node')
            if len(stack):
                if type(curr.node) is Control or curr.node.type == 'out' or curr.node.type == 'in':
                    assert_b(((stack[-1].nodeid, curr.nodeid) not in self.connections_q) ==
                        ((stack[-1].nodeid, curr.nodeid, condition) not in self.connections),
                        "two ways from %s to %s" % (nodename_n(stack[-1].node), nodename_n(curr.node)))
                    if ((stack[-1].nodeid, curr.nodeid) in self.connections_q) and \
                        ((stack[-1].nodeid, curr.nodeid, condition) in self.connections):
                        # print "repeat ", (stack[-1].nodeid, curr.nodeid, condition)
                        no_depth = True
                    if (stack[-1].nodeid, curr.nodeid, condition) not in self.connections:
                        self.connections.append((stack[-1].nodeid, curr.nodeid, condition))
                    self.connections_q.append((stack[-1].nodeid, curr.nodeid))
                    stack.pop()
                    condition = True
            if not no_depth:
                self._make(start + 1, stack + [curr], full_stack + [curr], condition, condition_stack)

        elif type(curr) is Jump and curr.dir == ARROW_UP:
            if type(full_stack[-1]) is CertainNode and full_stack[-1].node.type == "in":
                cond = True

                self._make(start + 1, stack[:], full_stack + [curr], cond, condition_stack[:] + full_stack[-1].node.signals)
                assert_b(curr.index in self.jump_down, "no arrow down [%d]" % curr.index)
                self._make(self.jump_down[curr.index], stack[:], full_stack + [curr], not cond, self._invert(condition_stack[:] + full_stack[-1].node.signals))
            else:
                assert_b(curr.index in self.jump_down, "no arrow down [%d]" % curr.index)
                self._make(self.jump_down[curr.index], stack[:], full_stack + [curr], condition, condition_stack)
        elif type(curr) is Jump and curr.dir == ARROW_DOWN:
            # print ">>$>", curr
            self._make(start + 1, stack[:], full_stack + [curr], condition, condition_stack)
        else:
            print "wtf: ", curr
            raise LSAAlgorithmError("WTF")

    def _build_table(self):
        # build matrix of connectivity
        self.matrix = [[None for y in self.barenodes] for x in self.barenodes]
        for c in self.connections:
            self.matrix[c[0]-1][c[1]-1] = c[2]
        # print self.matrix
        def _translate_node_to_index(s):
            if type(s.node) is Control:
                return -1
            return s.node.signals[0].index

        self.signals = {k:_translate_node_to_index(n) for k,n in self.barenodes.iteritems()}

    def analysis(self):
        self.enumerated = []
        nodeid = 0
        self.barenodes = {}
        for nid,s in enumerate(self.parsed):
            if type(s) is not Jump:
                if type(s) == Control or (type(s) == Node):
                    nodeid += 1
                    cnode = CertainNode(id=nid+1, nodeid=nodeid, node=s)
                    self.barenodes[nodeid] = cnode
                    self.enumerated.append(cnode)
                else:
                    self.enumerated.append(CertainNode(id=nid+1, nodeid=0, node=s))
            else:
                self.enumerated.append(s)

        self.out_signals = list(set(chain(*[e.signals for e in self.parsed if type(e) is Node and e.type=='out'])))
        self.in_signals = list(set(chain(*[e.signals for e in self.parsed if type(e) is Node and e.type=='in'])))
        self.arrow_up = [e for e in self.parsed if type(e) is Jump and e.dir==ARROW_UP]
        self.arrow_down = [e for e in self.parsed if type(e) is Jump and e.dir==ARROW_DOWN]
        self.signal_sanity_check(self.out_signals)
        self.signal_sanity_check(self.in_signals)
        self.arrow_sanity_check(self.arrow_up)
        self.arrow_sanity_check(self.arrow_down)
        arrow_down_indexes = {x.index for x in self.arrow_down}
        assert_b(len(arrow_down_indexes) == len(self.arrow_down), "Several DOWN arrows not allowed!")

        stack = []
        for s in self.parsed:
            if type(s) is Control and not len(stack):
                stack.append(s)
            elif type(s) is CertainNode and s.node.type == 'out':
                stack.append(s)

        self.jump_up = []
        self.jump_down = {}
        for i,s in enumerate(self.parsed):
            if type(s) == Jump and s.dir == ARROW_UP:
                self.jump_up.append((s.index, i))
            if type(s) == Jump and s.dir == ARROW_DOWN:
                self.jump_down[s.index] = i

        self._make(0)
        self._build_table()
        loops = self.find_infinite_loops()
        self.loop = None

        node_names = {k:nodename(k, {k: x}) for k,x in self.barenodes.iteritems()}

        if loops:
            loop = '->'.join([node_names[i+1] for i in loops[0]])
            warn = LSAAlgorithmWarning("Infinite loop found! %s" % loop)
            warn.tag = 'LOOP'
            warn.loop = loops[0]
            warnings.warn(warn)
            self.loop = loops[0]

        loops = []
        for i,x in enumerate(self.matrix):
            if not find_path(self.matrix, i, len(self.matrix)-1):
                loops.append(i)
        if loops:
            loop_s = '->'.join([node_names[i+1] for i in loops])
            warn = LSAAlgorithmWarning("Infinite loop found (2-way)! %s" % loop_s)
            warnings.warn(warn)
            self.loop = loops

    def _restore(self, x=0, fr=0):
        if x == 0:
            print "start"
            self.r_arrow_num = 0
        else:
            print "DOWN", fr

        self.r_arrow_num += 1
        for y,el in enumerate(self.matrix[x]):
            if el is not None:
                print x, '->', y
                self.r_arrow_num += 1
                if len(el):
                    print el
                print "UP", self.r_arrow_num
                self._restore(y, self.r_arrow_num)

    def restore(self):
        self._restore()

    def find_loops(self):
        loops = graph_analyse.find_loops(self.matrix)
        loops = list(set([tuple(graph_analyse.loop_from_looppath(x)) for x in loops]))
        return loops

    def find_infinite_loops(self):
        return graph_analyse.find_infinite_loops(self.matrix)

    def find_paths(self):
        return graph_analyse.find_paths(self.matrix) + graph_analyse.find_loops(self.matrix)


if __name__ == '__main__':
    s =  u'\u25cbX\u2081\u2191\xb9\u2193\xb2Y\u2081X\u2082\u2191\xb2Y\u2081\u2191\xb2\u2193\xb9\u25cf'
    print s
    p = LSAAnalyser(parse(s))
    p.analysis()
    # print p.matrix
    # print p.signals
    # print p.loop

    # print graph_analyse.find_loops(p.matrix)
    # print graph_analyse.find_paths(p.matrix)
    # print graph_analyse.find_infinite_loops(p.matrix)
