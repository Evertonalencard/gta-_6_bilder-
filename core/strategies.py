"""Strategy: como achar caminhos aumentantes (DFS = Ford-Fulkerson classico, BFS = Edmonds-Karp)."""
from abc import ABC, abstractmethod
from collections import deque


class AugmentingPathStrategy(ABC):
    @abstractmethod
    def find_path(self, net, s, t): ...

    @staticmethod
    def _rebuild(parent, t):
        if t not in parent:
            return None
        path, v = [], t
        while parent[v] is not None:
            u, i = parent[v]
            path.append((u, i))
            v = u
        return path[::-1]


class DFSPaths(AugmentingPathStrategy):
    def find_path(self, net, s, t):
        parent, stack = {s: None}, [s]
        while stack:
            u = stack.pop()
            if u == t:
                break
            for i, e in enumerate(net.graph[u]):
                if e.residual > 0 and e.to not in parent:
                    parent[e.to] = (u, i)
                    stack.append(e.to)
        return self._rebuild(parent, t)


class BFSPaths(AugmentingPathStrategy):
    def find_path(self, net, s, t):
        parent, q = {s: None}, deque([s])
        while q and t not in parent:
            u = q.popleft()
            for i, e in enumerate(net.graph[u]):
                if e.residual > 0 and e.to not in parent:
                    parent[e.to] = (u, i)
                    q.append(e.to)
        return self._rebuild(parent, t)
