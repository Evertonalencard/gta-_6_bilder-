"""NeonFlow — verificador em Python do Ford-Fulkerson (implementado do zero, sem bibliotecas de grafos).

Lê o JSON exportado pelo planejador (aba Arquivo) e imprime:
  * fluxo máximo (DFS = Ford-Fulkerson clássico, ou BFS = Edmonds-Karp)
  * vias saturadas (c_f(u,v) = 0) e corte mínimo
  * Cenário A (interdição / faixa bloqueada) e Cenário B (melhor obra de +X veíc/h)

Uso:
  python ford_fulkerson.py                      (usa mapa-south-beach.json)
  python ford_fulkerson.py mapa-neonflow.json
  python ford_fulkerson.py mapa-neonflow.json --metodo bfs
  python ford_fulkerson.py --interditar r40                 (uma rua interditada)
  python ford_fulkerson.py --interditar r35 --reduzir r19=50 (várias ruas ao mesmo tempo)
  python ford_fulkerson.py mapa-neonflow.json --obra 800
"""
import argparse
import os
import json
import sys
from collections import deque

INF = 10 ** 9
S, T = "__S", "__T"


class Aresta:
    """Aresta da rede residual. A reversa tem cap 0; residual = cap - flow."""
    __slots__ = ("para", "cap", "flow", "rev", "arco")

    def __init__(self, para, cap, arco):
        self.para, self.cap, self.flow, self.rev, self.arco = para, cap, 0, None, arco

    @property
    def residual(self):
        return self.cap - self.flow


class RedeResidual:
    def __init__(self):
        self.adj = {}

    def no(self, x):
        return self.adj.setdefault(x, [])

    def add(self, u, v, cap, arco=None):
        a, b = Aresta(v, cap, arco), Aresta(u, 0, None)
        a.rev, b.rev = b, a
        self.no(u).append(a)
        self.no(v).append(b)
        return a


def caminho_dfs(R, s, t):
    pai, pilha, vis = {}, [(s, iter(R.no(s)))], {s}
    while pilha:
        u, it = pilha[-1]
        if u == t:
            break
        for e in it:
            if e.residual > 0 and e.para not in vis:
                vis.add(e.para)
                pai[e.para] = e
                pilha.append((e.para, iter(R.no(e.para))))
                break
        else:
            pilha.pop()
    if t not in pai:
        return None
    caminho, v = [], t
    while v != s:
        e = pai[v]
        caminho.append(e)
        v = e.rev.para
    return caminho[::-1]


def caminho_bfs(R, s, t):
    pai, fila = {s: None}, deque([s])
    while fila and t not in pai:
        u = fila.popleft()
        for e in R.no(u):
            if e.residual > 0 and e.para not in pai:
                pai[e.para] = e
                fila.append(e.para)
    if t not in pai:
        return None
    caminho, v = [], t
    while v != s:
        e = pai[v]
        caminho.append(e)
        v = e.rev.para
    return caminho[::-1]


def arcos(mapa, over=None):
    over = over or {}
    out = []
    for r in mapa["roads"]:
        f = r["id"] + ">"
        out.append((f, r["id"], r["u"], r["v"], over.get(f, r["cap"])))
        if r.get("twoWay"):
            b = r["id"] + "<"
            out.append((b, r["id"], r["v"], r["u"], over.get(b, r["cap"])))
    return out


def fluxo_maximo(mapa, over=None, metodo="dfs"):
    lista = arcos(mapa, over)
    R, direta = RedeResidual(), {}
    for aid, _, u, v, c in lista:
        if c > 0 and u != v:
            direta[aid] = R.add(u, v, c, aid)
    for n in mapa["nodes"]:
        if n.get("role") == "src":
            R.add(S, n["id"], INF)
        elif n.get("role") == "snk":
            R.add(n["id"], T, INF)
    busca = caminho_bfs if metodo == "bfs" else caminho_dfs
    total, aumentos = 0, 0
    while (p := busca(R, S, T)) is not None:
        b = min(e.residual for e in p)           # gargalo do caminho aumentante
        for e in p:
            e.flow += b
            e.rev.flow -= b                       # mantém a rede residual explícita
        total += b
        aumentos += 1
    lado_s, pilha = {S}, [S]
    while pilha:
        u = pilha.pop()
        for e in R.no(u):
            if e.residual > 0 and e.para not in lado_s:
                lado_s.add(e.para)
                pilha.append(e.para)
    fluxo = {aid: (direta[aid].flow if aid in direta else 0) for aid, *_ in lista}
    for r in mapa["roads"]:                       # cancela fluxos opostos na mesma rua
        if r.get("twoWay"):
            m = min(fluxo[r["id"] + ">"], fluxo[r["id"] + "<"])
            fluxo[r["id"] + ">"] -= m
            fluxo[r["id"] + "<"] -= m
    info = [dict(id=a, road=rd, u=u, v=v, cap=c, flow=fluxo[a]) for a, rd, u, v, c in lista]
    saturadas = [a for a in info if a["cap"] > 0 and a["cap"] == a["flow"]]
    corte = [a for a in info if a["cap"] > 0 and a["u"] in lado_s and a["v"] not in lado_s]
    return total, aumentos, info, saturadas, corte


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mapa", nargs="?", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "mapa-south-beach.json"),
                    help="JSON exportado pelo planejador (padrão: mapa-south-beach.json)")
    ap.add_argument("--metodo", choices=["dfs", "bfs"], default="dfs")
    ap.add_argument("--interditar", nargs="+", default=[], metavar="RUA",
                    help="Cenário A: ruas interditadas por completo (ex.: --interditar r40 r35)")
    ap.add_argument("--reduzir", nargs="+", default=[], metavar="RUA=PCT",
                    help="Cenário A: ruas com fluxo diminuído em PCT%% (ex.: --reduzir r19=50 r12=30)")
    ap.add_argument("--obra", type=int, help="Cenário B: acréscimo X em veíc/h")
    a = ap.parse_args()
    with open(a.mapa, encoding="utf-8") as fh:
        mapa = json.load(fh)
    nome = {n["id"]: n.get("name", n["id"]) for n in mapa["nodes"]}
    rua = {r["id"]: r for r in mapa["roads"]}
    rot = lambda x: f'{rua[x["road"]]["name"]}: {nome[x["u"]]} -> {nome[x["v"]]}'

    total, aug, info, sat, corte = fluxo_maximo(mapa, metodo=a.metodo)
    print(f"Mapa: {mapa.get('nome', '')} | {len(mapa['nodes'])} cruzamentos, {len(info)} arcos")
    print(f"Fluxo máximo ({a.metodo.upper()}): {total} veíc/h em {aug} caminhos aumentantes\n")
    print("Vias saturadas (c_f = 0):")
    for x in sat:
        print(f"  - {rot(x)}  [{x['flow']}/{x['cap']}]")
    soma = sum(x["cap"] for x in corte)
    print(f"\nCorte mínimo (soma = {soma}):")
    for x in corte:
        print(f"  - {rot(x)}  [c = {x['cap']}]")

    afetadas = [(rid, 0.0, "interditada") for rid in a.interditar]
    for item in a.reduzir:
        rid, _, pc = item.partition("=")
        pc = float(pc or 50)
        afetadas.append((rid, 1 - pc / 100, f"-{pc:g}%"))
    if afetadas:
        over = {}
        for rid, fator, _ in afetadas:
            r = rua[rid]
            over[rid + ">"] = int(r["cap"] * fator)
            if r.get("twoWay"):
                over[rid + "<"] = int(r["cap"] * fator)
        depois = fluxo_maximo(mapa, over, a.metodo)[0]
        desc = ", ".join(f"{rua[rid]['name']} ({txt})" for rid, _, txt in afetadas)
        print(f"\nCenário A — {desc}: {total} -> {depois} "
              f"(perda {total - depois} veíc/h = {100 * (total - depois) / total:.1f}%)")
    if a.obra:
        print(f"\nCenário B — +{a.obra} veíc/h em cada arco saturado:")
        ops = sorted(((fluxo_maximo(mapa, {x['id']: x['cap'] + a.obra}, a.metodo)[0] - total, x) for x in sat),
                     key=lambda t: -t[0])
        for g, x in ops:
            print(f"  +{g:5d}  {rot(x)}")
        if ops and ops[0][0] > 0:
            print(f"Recomendação: {rot(ops[0][1])} (+{ops[0][0]} veíc/h)")
        else:
            print("Nenhuma obra isolada aumenta o fluxo.")


if __name__ == "__main__":
    sys.exit(main())