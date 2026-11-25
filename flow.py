"""Ford-Fulkerson implementado do zero, com rede residual explicita (sem libs de grafos)."""
from collections import defaultdict, deque


class Edge:
    __slots__ = ("to", "cap", "flow", "rev", "key")

    def __init__(self, to, cap, rev, key=None):
        self.to = to        # vertice de destino
        self.cap = cap      # capacidade c(u,v) (0 nas arestas reversas)
        self.flow = 0       # f(u,v); na reversa vale -f(v,u)
        self.rev = rev      # indice da aresta reversa em graph[to]
        self.key = key      # identificador externo (None = aresta residual reversa)

    @property
    def residual(self):     # c_f(u,v) = c(u,v) - f(u,v)
        return self.cap - self.flow


class FlowNetwork:
    def __init__(self):
        self.graph = defaultdict(list)

    def add_edge(self, u, v, cap, key=None):
        if u == v:
            return
        iu, iv = len(self.graph[u]), len(self.graph[v])
        self.graph[u].append(Edge(v, cap, iv, key))
        self.graph[v].append(Edge(u, 0, iu, None))   # aresta residual reversa

    def _find_path(self, s, t, method):
        parent = {s: None}
        if method == "dfs":                         # Ford-Fulkerson classico
            stack = [s]
            while stack:
                u = stack.pop()
                if u == t:
                    break
                for i, e in enumerate(self.graph[u]):
                    if e.residual > 0 and e.to not in parent:
                        parent[e.to] = (u, i)
                        stack.append(e.to)
        else:                                       # Edmonds-Karp (FF com BFS)
            q = deque([s])
            while q and t not in parent:
                u = q.popleft()
                for i, e in enumerate(self.graph[u]):
                    if e.residual > 0 and e.to not in parent:
                        parent[e.to] = (u, i)
                        q.append(e.to)
        if t not in parent:
            return None
        path, v = [], t
        while parent[v] is not None:
            u, i = parent[v]
            path.append((u, i))
            v = u
        path.reverse()
        return path

    def max_flow(self, s, t, method="bfs"):
        total, augmentations = 0, 0
        while True:
            path = self._find_path(s, t, method)
            if path is None:
                break
            b = min(self.graph[u][i].residual for u, i in path)
            for u, i in path:
                e = self.graph[u][i]
                e.flow += b
                self.graph[e.to][e.rev].flow -= b
            total += b
            augmentations += 1
        return total, augmentations

    def reachable_from(self, s):
        """Lado S do corte minimo (apos max_flow)."""
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
