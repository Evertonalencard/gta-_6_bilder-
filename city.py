"""Estado do jogo: cidade, orcamento, vias, eventos e analise de fluxo."""
import random
from dataclasses import dataclass, field
from flow import FlowNetwork

S, T = "__S__", "__T__"
INF = 10**9

CAP_POR_FAIXA = {"rua": 600, "avenida": 800}         # veic/h por faixa (3 faixas av. ~ 2400)
FAIXAS_VALIDAS = {"rua": (1, 2), "avenida": (2, 4)}  # faixas POR SENTIDO
CUSTO_FAIXA = {"rua": 800, "avenida": 1800}          # por faixa, por sentido, por unidade de comprimento
CUSTO_CONSTRUCAO = {"casa": 500, "comercio": 800, "industria": 1200}
HAB_POR_CASA, VAGAS_COMERCIO, VAGAS_INDUSTRIA = 100, 80, 150
VIAGENS_POR_HAB = 0.6          # veiculos/h gerados por habitante no horario de pico
IMPOSTO_POR_HAB = 2.0
MAX_LOTES = 10
VERDE_ATE, AMARELO_ATE = 0.60, 0.90


class GameError(Exception):
    pass


@dataclass
class Node:
    id: int
    nome: str
    x: float
    y: float
    casas: int = 0
    comercios: int = 0
    industrias: int = 0
    estadio: bool = False
    saida: bool = False


@dataclass
class Road:
    id: int
    u: int
    v: int
    tipo: str = "rua"          # rua | avenida
    faixas: int = 1            # por sentido
    mao_unica: bool = False    # True: apenas u -> v
    comprimento: float = 1.0

    def cap(self):
        return self.faixas * CAP_POR_FAIXA[self.tipo]

    def sentidos(self):
        return [("fw", self.u, self.v)] + ([] if self.mao_unica else [("bw", self.v, self.u)])


@dataclass
class Event:
    id: int
    tipo: str                  # obra | acidente
    road_id: int
    fator: float               # 0.0 (interditada) ou 0.5 (faixa bloqueada)
    restante: int              # ciclos restantes


@dataclass
class City:
    verba: float = 20000
    ciclo: int = 0
    nodes: dict = field(default_factory=dict)
    roads: dict = field(default_factory=dict)
    events: dict = field(default_factory=dict)
    _rid: int = 0
    _eid: int = 0
    rng: random.Random = field(default_factory=random.Random)

    # ---------- consultas ----------
    @property
    def populacao(self):
        return sum(n.casas for n in self.nodes.values()) * HAB_POR_CASA

    @property
    def vagas(self):
        return sum(n.comercios * VAGAS_COMERCIO + n.industrias * VAGAS_INDUSTRIA for n in self.nodes.values())

    def fator_evento(self, road_id):
        f = 1.0
        for e in self.events.values():
            if e.road_id == road_id:
                f = min(f, e.fator)
        return f

    def arestas(self):
        """Arestas orientadas efetivas: (key, u, v, capacidade_base, capacidade_efetiva)."""
        out = []
        for r in self.roads.values():
            f = self.fator_evento(r.id)
            for d, u, v in r.sentidos():
                out.append(((r.id, d), u, v, r.cap(), int(r.cap() * f)))
        return out

    def _gasta(self, valor):
        if valor > self.verba:
            raise GameError(f"Verba insuficiente: custa {valor:.0f}, voce tem {self.verba:.0f}.")
        self.verba -= valor

    # ---------- construcao ----------
    def construir(self, node_id, tipo):
        n = self.nodes.get(node_id)
        if not n:
            raise GameError("No inexistente.")
        campo = {"casa": "casas", "comercio": "comercios", "industria": "industrias"}.get(tipo)
        if not campo:
            raise GameError("Tipo invalido (casa | comercio | industria).")
        if getattr(n, campo) >= MAX_LOTES:
            raise GameError("Limite de lotes neste cruzamento.")
        self._gasta(CUSTO_CONSTRUCAO[tipo])
        setattr(n, campo, getattr(n, campo) + 1)

    def _custo_via(self, tipo, faixas, mao_unica, comp):
        return CUSTO_FAIXA[tipo] * faixas * (1 if mao_unica else 2) * comp

    def _valida(self, tipo, faixas):
        if tipo not in FAIXAS_VALIDAS:
            raise GameError("tipo deve ser 'rua' ou 'avenida'.")
        lo, hi = FAIXAS_VALIDAS[tipo]
        if not lo <= faixas <= hi:
            raise GameError(f"{tipo} aceita de {lo} a {hi} faixas por sentido.")

    def construir_via(self, u, v, tipo, faixas, mao_unica):
        if u not in self.nodes or v not in self.nodes or u == v:
            raise GameError("Nos invalidos.")
        if any({r.u, r.v} == {u, v} for r in self.roads.values()):
            raise GameError("Ja existe via entre estes cruzamentos (melhore-a).")
        self._valida(tipo, faixas)
        a, b = self.nodes[u], self.nodes[v]
        comp = max(0.5, round(((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5, 2))
        self._gasta(self._custo_via(tipo, faixas, mao_unica, comp))
        self._rid += 1
        r = Road(self._rid, u, v, tipo, faixas, mao_unica, comp)
        self.roads[r.id] = r
        return r

    def melhorar_via(self, road_id, tipo=None, faixas=None):
        r = self._road(road_id)
        tipo, faixas = tipo or r.tipo, faixas or r.faixas
        self._valida(tipo, faixas)
        if tipo == r.tipo and faixas <= r.faixas:
            raise GameError("Melhoria deve aumentar a capacidade.")
        if CAP_POR_FAIXA[tipo] * faixas <= r.cap():
            raise GameError("Nova configuracao nao aumenta a capacidade.")
        novo = self._custo_via(tipo, faixas, r.mao_unica, r.comprimento)
        velho = self._custo_via(r.tipo, r.faixas, r.mao_unica, r.comprimento)
        self._gasta(max(300, novo - 0.5 * velho))
        r.tipo, r.faixas = tipo, faixas
        return r

    def inverter_via(self, road_id):
        r = self._road(road_id)
        if not r.mao_unica:
            raise GameError("So vias de mao unica podem ser invertidas.")
        r.u, r.v = r.v, r.u
        return r

    def definir_mao(self, road_id, mao_unica):
        r = self._road(road_id)
        if r.mao_unica and not mao_unica:
            self._gasta(self._custo_via(r.tipo, r.faixas, False, r.comprimento) * 0.5)
        r.mao_unica = mao_unica
        return r

    def _road(self, rid):
        if rid not in self.roads:
            raise GameError("Via inexistente.")
        return self.roads[rid]

    # ---------- analise de fluxo ----------
    def montar_rede(self, fontes, sorvedouros, overrides=None):
        net = FlowNetwork()
        for _, u, v, _, cap in self.arestas():
            pass
        for key, u, v, _, cap in self.arestas():
            c = (overrides or {}).get(key, cap)
            if c > 0:
                net.add_edge(u, v, c, key)
        for n, d in fontes.items():
            net.add_edge(S, n, d)
        for n, c in sorvedouros.items():
            net.add_edge(n, T, c)
        return net

    def demanda_diaria(self):
        """Pico normal: casas geram viagens; comercio/industria sao os destinos."""
        fontes = {n.id: n.casas * HAB_POR_CASA * VIAGENS_POR_HAB for n in self.nodes.values() if n.casas}
        sink = {n.id: (n.comercios * VAGAS_COMERCIO + n.industrias * VAGAS_INDUSTRIA) * VIAGENS_POR_HAB
                for n in self.nodes.values() if n.comercios or n.industrias}
        return {k: int(v) for k, v in fontes.items()}, {k: int(v) for k, v in sink.items()}

    def demanda_evento(self, veiculos):
        est = [n.id for n in self.nodes.values() if n.estadio]
        sai = [n.id for n in self.nodes.values() if n.saida]
        if not est or not sai:
            raise GameError("O mapa precisa de um estadio e ao menos uma saida.")
        return {est[0]: int(veiculos)}, {s: INF for s in sai}

    def analisar(self, fontes, sorvedouros, overrides=None, metodo="bfs", detalhar=True):
        net = self.montar_rede(fontes, sorvedouros, overrides)
        fluxo, aug = net.max_flow(S, T, metodo)
        demanda = sum(fontes.values())
        res = {"fluxo_maximo": fluxo, "demanda": demanda,
               "atendimento": round(fluxo / demanda, 4) if demanda else 1.0,
               "aumentos": aug}
        if not detalhar:
            return res, net
        por_key = {e.key: e for _, e in net.forward_edges()}
        base = {k: (u, v, cb) for k, u, v, cb, _ in self.arestas()}
        vias, saturadas = [], []
        for key, (u, v, cap_base) in base.items():
            e = por_key.get(key)
            cap = e.cap if e else 0
            f = e.flow if e else 0
            util = (f / cap) if cap > 0 else 1.0
            cor = "cinza" if cap == 0 else "verde" if util < VERDE_ATE else "amarelo" if util < AMARELO_ATE else "vermelho"
            item = {"via": key[0], "sentido": key[1], "de": u, "para": v, "capacidade": cap,
                    "capacidade_base": cap_base, "fluxo": f, "residual": cap - f,
                    "utilizacao": round(util, 3), "cor": cor, "saturada": cap > 0 and f == cap}
            vias.append(item)
            if item["saturada"]:
                saturadas.append(item)
        lado_s = net.reachable_from(S)
        corte = [i for i in vias if i["de"] in lado_s and i["para"] not in lado_s and i["capacidade"] > 0]
        res.update({"vias": vias, "vias_saturadas": saturadas, "corte_minimo": corte})
        return res, net

    # ---------- cenarios "e se?" ----------
    def cenario_a(self, fontes, sorvedouros, road_id, modo, sentido=None, metodo="bfs"):
        r = self._road(road_id)
        fator = {"interditar": 0.0, "faixa": 0.5}.get(modo)
        if fator is None:
            raise GameError("modo deve ser 'interditar' ou 'faixa'.")
        antes, _ = self.analisar(fontes, sorvedouros, metodo=metodo, detalhar=False)
        ov = {(r.id, d): int(r.cap() * fator) for d, _, _ in r.sentidos() if sentido in (None, d)}
        depois, _ = self.analisar(fontes, sorvedouros, overrides=ov, metodo=metodo, detalhar=False)
        perda = antes["fluxo_maximo"] - depois["fluxo_maximo"]
        pct = round(100 * perda / antes["fluxo_maximo"], 2) if antes["fluxo_maximo"] else 0.0
        return {"via": road_id, "modo": modo, "fluxo_antes": antes["fluxo_maximo"],
                "fluxo_depois": depois["fluxo_maximo"], "perda_veic_h": perda, "perda_percentual": pct}

    def cenario_b(self, fontes, sorvedouros, x, metodo="bfs"):
        base, _ = self.analisar(fontes, sorvedouros, metodo=metodo)
        ranking = []
        for e in base["vias_saturadas"]:
            key = (e["via"], e["sentido"])
            novo, _ = self.analisar(fontes, sorvedouros, overrides={key: e["capacidade"] + x},
                                    metodo=metodo, detalhar=False)
            ganho = novo["fluxo_maximo"] - base["fluxo_maximo"]
            ranking.append({"via": e["via"], "sentido": e["sentido"], "de": e["de"], "para": e["para"],
                            "capacidade_atual": e["capacidade"], "capacidade_nova": e["capacidade"] + x,
                            "fluxo_novo": novo["fluxo_maximo"], "ganho": ganho})
        ranking.sort(key=lambda r: r["ganho"], reverse=True)
        melhor = ranking[0] if ranking and ranking[0]["ganho"] > 0 else None
        return {"fluxo_atual": base["fluxo_maximo"], "x": x, "ranking": ranking, "recomendacao": melhor}

    # ---------- tempo, orcamento, eventos ----------
    def avancar_ciclo(self):
        res, _ = self.analisar(*self.demanda_diaria(), detalhar=False)
        imposto = round(self.populacao * IMPOSTO_POR_HAB * res["atendimento"], 2)
        self.verba += imposto
        self.ciclo += 1
        for e in list(self.events.values()):
            e.restante -= 1
            if e.restante <= 0:
                del self.events[e.id]
        novo = None
        if self.roads and self.rng.random() < 0.4:
            r = self.rng.choice(list(self.roads.values()))
            tipo, fator = self.rng.choice([("obra", 0.0), ("acidente", 0.5)])
            self._eid += 1
            novo = Event(self._eid, tipo, r.id, fator, self.rng.randint(2, 4))
            self.events[novo.id] = novo
        return {"ciclo": self.ciclo, "imposto": imposto, "verba": self.verba,
                "atendimento": res["atendimento"], "novo_evento": novo.__dict__ if novo else None}

    def horario_pico(self, veiculos):
        fontes, sinks = self.demanda_evento(veiculos)
        res, _ = self.analisar(fontes, sinks)
        a = res["atendimento"]
        status = "sucesso" if res["fluxo_maximo"] >= res["demanda"] else "congestionada" if a >= 0.7 else "travou"
        bonus = 0
        if status == "sucesso":
            bonus = round(veiculos * 0.5)
            self.verba += bonus
        res.update({"status": status, "bonus": bonus, "verba": self.verba})
        return res

    def to_dict(self):
        return {"verba": self.verba, "ciclo": self.ciclo, "populacao": self.populacao, "vagas": self.vagas,
                "empregados_sem_destino": max(0, self.populacao - self.vagas),
                "nos": [n.__dict__ for n in self.nodes.values()],
                "vias": [{**r.__dict__, "capacidade_por_sentido": r.cap()} for r in self.roads.values()],
                "eventos": [e.__dict__ for e in self.events.values()]}


def cidade_exemplo(seed=None):
    """Grade 4x5 = 20 cruzamentos. Troque por dados do OpenStreetMap (ver carregar_json)."""
    c = City(rng=random.Random(seed))
    R, C = 4, 5
    for r in range(R):
        for q in range(C):
            c.nodes[r * C + q] = Node(r * C + q, f"Cruzamento {r * C + q}", q, r)
    c.nodes[0].estadio = True; c.nodes[0].nome = "Estadio"
    for i in (4, 19):
        c.nodes[i].saida = True; c.nodes[i].nome = "Saida"
    for i in (5, 6, 10, 11, 15, 16):
        c.nodes[i].casas = 3
    for i in (7, 8, 12, 13):
        c.nodes[i].comercios = 4
    for i in (9, 14, 18):
        c.nodes[i].industrias = 3

    def via(u, v, tipo="rua", faixas=1, unica=False):
        c._rid += 1
        a, b = c.nodes[u], c.nodes[v]
        c.roads[c._rid] = Road(c._rid, u, v, tipo, faixas, unica, max(0.5, abs(a.x - b.x) + abs(a.y - b.y)))

    for r in range(R):
        for q in range(C):
            i = r * C + q
            if q + 1 < C:
                av = r == 1
                via(i, i + 1, "avenida" if av else "rua", 2 if av else 1)
            if r + 1 < R:
                av = q == 2
                via(i, i + C, "avenida" if av else "rua", 2 if av else 1, unica=(q == 4))
    return c
