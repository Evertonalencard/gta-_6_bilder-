"""Rede de fluxo com rede residual explicita (Ford-Fulkerson do zero, sem libs de grafos)."""
from collections import defaultdict


class Edge:
    __slots__ = ("to", "cap", "flow", "rev", "key")

    def __init__(self, to, cap, rev, key=None):
        self.to, self.cap, self.flow, self.rev, self.key = to, cap, 0, rev, key

    @property
    def residual(self):            # c_f(u,v) = c(u,v) - f(u,v)
        return self.cap - self.flow


class FlowNetwork:
    def __init__(self):
        self.graph = defaultdict(list)

    def add_edge(self, u, v, cap, key=None):
        if u == v:
            return
        iu, iv = len(self.graph[u]), len(self.graph[v])
        self.graph[u].append(Edge(v, cap, iv, key))
        self.graph[v].append(Edge(u, 0, iu, None))      # aresta residual reversa

    def augment(self, path):
        b = min(self.graph[u][i].residual for u, i in path)
        for u, i in path:
            e = self.graph[u][i]
            e.flow += b
            self.graph[e.to][e.rev].flow -= b
        return b

    def max_flow(self, s, t, strategy):
        """strategy: AugmentingPathStrategy (Strategy)."""
        total = aug = 0
        while (path := strategy.find_path(self, s, t)) is not None:
            total += self.augment(path)
            aug += 1
        return total, aug

    def reachable_from(self, s):
        seen, stack = {s}, [s]
        while stack:
            u = stack.pop()
            for e in self.graph[u]:
                if e.residual > 0 and e.to not in seen:
                    seen.add(e.to)
                    stack.append(e.to)
        return seen

    def forward_edges(self):
        for u, edges in self.graph.items():
            for e in edges:
                if e.key is not None:
                    yield u, e
