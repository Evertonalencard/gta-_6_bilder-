"""Strategy: cada ferramenta decide o que um clique no mapa significa."""
from abc import ABC, abstractmethod

from core.domain import LotKind, RoadKind


class ToolContext:
    def __init__(self, controller, picker, proj, raio_no, tol_via):
        self.c, self.picker, self.proj = controller, picker, proj
        self.raio_no, self.tol_via = raio_no, tol_via       # funcoes de zoom -> tolerancia em unidades de mundo
        self.pendente = None                                # primeiro no da via em construcao
        self.selecao_via = None
        self.config_via = {"kind": RoadKind.RUA, "faixas": 1, "mao_unica": False}
        self.evento = True
        self.ultimo_relatorio_texto = ""
        self.rotacao_lote = 0.0


class Tool(ABC):
    nome = ""

    @abstractmethod
    def clique(self, ctx: ToolContext, wx: float, wy: float) -> str: ...


class SelecionarTool(Tool):
    nome = "Selecionar"

    def clique(self, ctx, wx, wy):
        rid = ctx.picker.via(wx, wy, ctx.tol_via())
        ctx.selecao_via = rid
        if rid is None:
            return "Nada selecionado."
        r = ctx.c.city.roads[rid]
        return (f"Via {rid}: {r.kind.rotulo} {r.faixas} faixa(s), {'mao unica' if r.mao_unica else 'mao dupla'}, "
                f"cap {r.cap_efetiva}/{r.cap_base} pessoas/h, estado: {r.state.nome}")


class CameraTool(Tool):
    nome = "Camera"

    def clique(self, ctx, wx, wy):
        return "Arraste o mapa para navegar; use a roda para zoom."


class CruzamentoTool(Tool):
    nome = "Cruzamento"

    def clique(self, ctx, wx, wy):
        nx, ny = ctx.proj.to_norm(wx, wy)
        n = ctx.c.criar_cruzamento(nx, ny)
        return f"Cruzamento {n.id} criado."


class ViaTool(Tool):
    nome = "Via"

    def clique(self, ctx, wx, wy):
        no = ctx.picker.no(wx, wy, ctx.raio_no())
        if no is None:
            ctx.pendente = None
            return "Clique em um cruzamento."
        if ctx.pendente is None:
            ctx.pendente = no
            return "Escolha o cruzamento de destino."
        u, ctx.pendente = ctx.pendente, None
        r = ctx.c.construir_via(u, no, **ctx.config_via)
        return f"Via {r.id} construida."

    def arrastar(self, ctx, x1, y1, x2, y2):
        x1, y1 = ctx.proj.to_norm(x1, y1)
        x2, y2 = ctx.proj.to_norm(x2, y2)
        via = ctx.c.construir_via_por_coordenadas(x1, y1, x2, y2, **ctx.config_via)
        return f"Via {via.id} construida."


class LoteTool(Tool):
    def __init__(self, kind: LotKind):
        self.kind, self.nome = kind, f"Lote {kind.rotulo}"

    def clique(self, ctx, wx, wy):
        placement = self.previsualizar(ctx, wx, wy)
        if not placement.valid:
            return placement.reason
        ctx.c.construir_lote_posicionado(placement, ctx.proj.w, ctx.proj.h)
        return f"{self.kind.rotulo.capitalize()} construido."

    def previsualizar(self, ctx, wx, wy):
        return ctx.c.previsualizar_lote(
            wx, wy, self.kind, ctx.proj.w, ctx.proj.h, ctx.rotacao_lote
        )


class DemolirTool(Tool):
    nome = "Demolir"

    def clique(self, ctx, wx, wy):
        lot_id = ctx.picker.lote(wx, wy, ctx.proj.w, ctx.proj.h)
        if lot_id is not None:
            ctx.c.demolir_construcao(lot_id)
            return f"Lote {lot_id} demolido."
        node_id = ctx.picker.no(wx, wy, ctx.raio_no() * 2.5)
        if node_id is not None:
            node = ctx.c.city.nodes[node_id]
            for kind in (LotKind.INDUSTRIA, LotKind.COMERCIO, LotKind.CASA):
                if node.lotes(kind):
                    ctx.c.demolir_lote(node_id, kind)
                    return f"Lote {kind.rotulo} demolido."
        road_id = ctx.picker.via(wx, wy, ctx.tol_via())
        if road_id is not None:
            ctx.c.demolir_via(road_id)
            return f"Via {road_id} demolida."
        return "Clique em uma estrada ou lote."


class AcaoViaTool(Tool):
    """Ferramenta generica para acoes sobre uma via: melhorar, inverter, alternar mao, cenario A."""

    def __init__(self, nome, acao):
        self.nome, self.acao = nome, acao

    def clique(self, ctx, wx, wy):
        rid = ctx.picker.via(wx, wy, ctx.tol_via())
        if rid is None:
            return "Clique em uma via."
        ctx.selecao_via = rid
        return self.acao(ctx, rid)


def melhorar(ctx, rid):
    r = ctx.c.melhorar_via(rid)
    return f"Via {rid} agora e {r.kind.rotulo} com {r.faixas} faixa(s)."

def inverter(ctx, rid):
    ctx.c.inverter_via(rid)
    return f"Sentido da via {rid} invertido."

def alternar(ctx, rid):
    r = ctx.c.alternar_mao(rid)
    return f"Via {rid}: {'mao unica' if r.mao_unica else 'mao dupla'}."

def cenario_a(ctx, rid):
    a = ctx.c.cenario_a(rid, "interditar", ctx.evento)
    return f"Interditar via {rid}: {a.fluxo_antes} -> {a.fluxo_depois} veic/h (perda {a.perda_percentual:.1f}%)."

def cenario_a_faixa(ctx, rid):
    a = ctx.c.cenario_a(rid, "faixa", ctx.evento)
    return f"Faixa bloqueada na via {rid}: {a.fluxo_antes} -> {a.fluxo_depois} veic/h (perda {a.perda_percentual:.1f}%)."
