import math

import arcade

from core import events as ev
from core.domain import LotKind, RoadKind
from core.errors import GameError
from .camera import CameraController
from .panel import ControlPanel
from .projection import MapProjection, Picker
from .renderers import BaseMapRenderer, CarSwarm, LotRenderer, RoadRenderer
from . import tools as T


class GameView(arcade.View):
    """Renderiza a cidade e encaminha interacoes ao controller injetado."""

    def __init__(self, controller, mapa_png):
        super().__init__()
        self.c = controller
        self.base = BaseMapRenderer(mapa_png)
        self.proj = MapProjection(self.base.w, self.base.h)
        self.camera = CameraController(self.window, self.base.w, self.base.h)
        self.picker = Picker(controller.city, self.proj)
        escala = self.base.w / 1650
        self.roads = RoadRenderer(controller.city, self.proj, escala)
        self.lots = LotRenderer(controller.city, self.proj, escala)
        self.cars = CarSwarm(controller.city, self.proj, escala)
        self.ctx = T.ToolContext(
            controller, self.picker, self.proj,
            lambda: 8 * self.base.w / 1650 / self.camera.cam.zoom * 3,
            lambda: 6 * self.base.w / 1650 / self.camera.cam.zoom * 2,
        )
        self.tool = T.SelecionarTool()
        self.report = None
        self.evento_ativo = False
        self.sujo = True
        self.paused = True
        self._auto_clock = 0.0
        self._mouse_start = None
        self._drag_end = None
        self._mouse_world = None
        self.lote_preview = None
        self.panel = ControlPanel()
        self._montar_painel()
        for topico in (ev.CITY_CHANGED, ev.BUDGET_CHANGED, ev.CYCLE_ADVANCED, ev.RUSH_FINISHED):
            controller.bus.subscribe(topico, self._on_evento)
        controller.bus.subscribe(
            ev.ROAD_EVENT_STARTED,
            lambda road_id, tipo, duracao: self.panel.mensagem(
                f"Evento: {tipo} na via {road_id}, {duracao} ciclos"
            ),
        )
        pontos = [self.proj.to_world(n.x, n.y) for n in controller.city.nodes.values()]
        if pontos:
            self.camera.focar(
                sum(p[0] for p in pontos) / len(pontos),
                sum(p[1] for p in pontos) / len(pontos),
                6.0,
            )

    def _montar_painel(self):
        p = self.panel
        p.add_status_action("pause", "", "▶", self._alternar_pausa)
        p.add_status_action("advance", "", "▶", lambda: self._avancar(False))
        p.add_status_action("peak", "", "≫", lambda: self._avancar(True))
        p.add_demolition_action(
            "demolish", "Demolir", "×",
            lambda: self._selecionar_tool(T.DemolirTool(), "demolish"),
        )
        p.add_category("roads", "Estradas", "╱", lambda: self._alternar_categoria("roads"))
        p.add_category("lots", "Construcoes e loteamento", "⌂",
                       lambda: self._alternar_categoria("lots"))

        for key, label, icon, kind, lanes in (
            ("street-1", "Rua de 1 faixa", "━", RoadKind.RUA, 1),
            ("street-2", "Rua de 2 faixas", "═", RoadKind.RUA, 2),
            ("avenue-2", "Avenida de 2 faixas", "▰", RoadKind.AVENIDA, 2),
            ("avenue-4", "Avenida de 4 faixas", "▰", RoadKind.AVENIDA, 4),
        ):
            p.add_action(
                "roads", key, label, icon,
                lambda k=kind, f=lanes, action_key=key: self._configurar_via(k, f, action_key),
            )
        p.add_action(
            "roads", "improve", "Melhorar", "+",
            lambda: self._selecionar_tool(T.AcaoViaTool("Melhorar", T.melhorar), "improve"),
        )
        p.add_action(
            "roads", "one-way", "Mao unica", "→", self._alternar_mao,
        )
        p.add_action(
            "roads", "invert", "Inverter", "↔",
            lambda: self._selecionar_tool(T.AcaoViaTool("Inverter", T.inverter), "invert"),
        )
        p.add_action(
            "roads", "two-way", "Alternar mao", "⇄",
            lambda: self._selecionar_tool(T.AcaoViaTool("Alternar", T.alternar), "two-way"),
        )
        p.add_action("roads", "event", "Demanda evento", "⚡", self._alternar_modo)
        p.add_action(
            "roads", "scenario-a", "Fechar via", "×",
            lambda: self._selecionar_tool(
                T.AcaoViaTool("A", T.cenario_a), "scenario-a"
            ),
        )
        p.add_action(
            "roads", "scenario-a-lane", "Bloquear faixa", "╳",
            lambda: self._selecionar_tool(
                T.AcaoViaTool("A2", T.cenario_a_faixa), "scenario-a-lane"
            ),
        )
        p.add_action("roads", "scenario-b", "Obra sugerida", "?", self._cenario_b)
        p.add_action("roads", "save", "Salvar mapa", "↓", self._salvar)

        for key, label, icon, kind in (
            ("home", "Casa", "⌂", LotKind.CASA),
            ("commerce", "Comercio", "C", LotKind.COMERCIO),
            ("industry", "Industria", "I", LotKind.INDUSTRIA),
        ):
            p.add_action(
                "lots", key, label, icon,
                lambda k=kind, action_key=key: self._selecionar_tool(T.LoteTool(k), action_key),
            )

        p.set_status("money", "0")
        p.set_status("population", "0")
        p.set_status("cycle", "Ciclo 0")
        p.set_status("flow", "Fluxo 0")
        p.set_status("simulation", "Pausado")
        p.mensagem("Pan: botao direito/meio ou WASD. Lotes: mova, pressione R para girar, clique para confirmar.")

    def _alternar_categoria(self, categoria):
        self.panel.set_category(None if self.panel.category == categoria else categoria)
        self.lote_preview = None

    def _selecionar_tool(self, tool, key):
        self.tool = tool
        self.ctx.pendente = None
        self.panel.set_active(key)
        self.lote_preview = None
        self.panel.mensagem(f"Ferramenta: {tool.nome}.")
        self._atualizar_lote_preview()

    def _configurar_via(self, kind, faixas, key):
        self.ctx.config_via.update(kind=kind, faixas=faixas)
        self._selecionar_tool(T.ViaTool(), key)
        self.panel.mensagem(
            f"{kind.rotulo.capitalize()} {faixas} faixa(s), "
            f"{kind.capacidade_base} pessoas/h por sentido. Arraste no mapa."
        )

    def _alternar_mao(self):
        self.ctx.config_via["mao_unica"] = not self.ctx.config_via["mao_unica"]
        modo = "unica" if self.ctx.config_via["mao_unica"] else "dupla"
        self.panel.mensagem(f"Novas vias: mao {modo}.")

    def _alternar_modo(self):
        self.evento_ativo = not self.evento_ativo
        self.ctx.evento = self.evento_ativo
        self.sujo = True
        self.panel.mensagem(f"Demanda: {'evento' if self.evento_ativo else 'rotina'}.")

    def _alternar_pausa(self):
        self.paused = not self.paused
        self._auto_clock = 0.0
        self.panel.set_action_icon("pause", "▶" if self.paused else "Ⅱ")
        self.panel.set_status("simulation", "Pausado" if self.paused else "Rodando")
        self.panel.mensagem(
            "Simulacao pausada." if self.paused else "Simulacao rodando; avance manualmente quando quiser."
        )

    def _salvar(self):
        from core.factories import CityRepository
        CityRepository("data/mapa.json").salvar(self.c.city)
        self.panel.mensagem("Mapa salvo em data/mapa.json.")

    def _cenario_b(self):
        try:
            atual, _, melhor = self.c.cenario_b(600, self.evento_ativo)
        except GameError as error:
            self.panel.mensagem(str(error))
            return
        if not melhor:
            self.panel.mensagem("Nenhuma obra melhora o fluxo atual.")
        else:
            self.panel.mensagem(
                f"Alargue a via {melhor.key[0]}: {atual} -> "
                f"{melhor.fluxo_novo} pessoas/h (+{melhor.ganho})."
            )

    def _avancar(self, pico):
        try:
            resultado = self.c.avancar_tempo(pico)
        except GameError as error:
            self.panel.mensagem(str(error))
            return
        if resultado:
            self.evento_ativo = True
            self.ctx.evento = True
            self.panel.mensagem(
                f"PICO: {resultado.status.upper()} - "
                f"{resultado.report.fluxo_maximo}/{resultado.report.demanda} pessoas/h "
                f"(+{resultado.bonus:.0f} verba)"
            )

    def _atualizar_lote_preview(self):
        if not isinstance(self.tool, T.LoteTool) or self._mouse_world is None:
            self.lote_preview = None
            return
        self.lote_preview = self.tool.previsualizar(self.ctx, *self._mouse_world)

    def _on_evento(self, **_):
        self.sujo = True

    def _atualizar(self):
        self.report = self.c.analisar(self.evento_ativo)
        self.cars.reconstruir(self.report)
        self.panel.set_status("money", f"{self.c.treasury.saldo:,.0f}")
        self.panel.set_status("population", f"{self.c.city.populacao:,}")
        self.panel.set_status("cycle", f"Ciclo {self.c.ciclo}")
        self.panel.set_status("flow", f"Fluxo {self.report.fluxo_maximo:,}")
        self.sujo = False

    def on_show_view(self):
        self.window.background_color = (30, 140, 170)

    def on_update(self, dt):
        if self.sujo:
            self._atualizar()
        if not self.paused:
            self._auto_clock += dt
            if self._auto_clock >= 5:
                self._auto_clock = 0
                self._avancar(False)
        self.camera.update(dt)
        self.cars.update(dt)

    def on_draw(self):
        self.clear()
        self.camera.use()
        self.base.draw()
        self.roads.draw(self.report, self.ctx.selecao_via)
        self.cars.draw()
        self.lots.draw(self.lote_preview)
        if self._mouse_start and self._drag_end:
            arcade.draw_line(*self._mouse_start, *self._drag_end, (60, 120, 230, 190), 4)
        self.window.default_camera.use()
        self.panel.draw(self.window.width)

    def on_resize(self, width, height):
        self.camera.resize()

    def on_mouse_scroll(self, x, y, scroll_x, scroll_y):
        self.camera.zoom_em(x, y, 1.15 if scroll_y > 0 else 1 / 1.15)

    def on_mouse_motion(self, x, y, dx, dy):
        if not self.panel.contains(x, y):
            self._mouse_world = self.camera.to_world(x, y)
            self._atualizar_lote_preview()
        else:
            self._mouse_world = None
            self.lote_preview = None

    def on_mouse_press(self, x, y, button, modifiers):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        if self.panel.handle_click(x, y, self.window.width):
            return
        if self.panel.contains(x, y):
            return
        wx, wy = self.camera.to_world(x, y)
        if isinstance(self.tool, T.ViaTool):
            self._mouse_start = (wx, wy)
            self._drag_end = (wx, wy)
            return
        try:
            self.panel.mensagem(self.tool.clique(self.ctx, wx, wy))
        except GameError as error:
            self.panel.mensagem(str(error))
        self._atualizar_lote_preview()

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        if buttons & (arcade.MOUSE_BUTTON_RIGHT | arcade.MOUSE_BUTTON_MIDDLE):
            self.camera.arrastar(dx, dy)
        elif buttons & arcade.MOUSE_BUTTON_LEFT and self._mouse_start and isinstance(self.tool, T.ViaTool):
            self._drag_end = self.camera.to_world(x, y)
        if not self.panel.contains(x, y):
            self._mouse_world = self.camera.to_world(x, y)
            self._atualizar_lote_preview()

    def on_mouse_release(self, x, y, button, modifiers):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return
        if isinstance(self.tool, T.ViaTool) and self._mouse_start:
            if self.panel.contains(x, y):
                self._mouse_start = self._drag_end = None
                return
            end = self.camera.to_world(x, y)
            start = self._mouse_start
            self._mouse_start = self._drag_end = None
            if (end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2 < 16:
                self.panel.mensagem("Arraste para desenhar a via.")
                return
            try:
                self.panel.mensagem(self.tool.arrastar(self.ctx, *start, *end))
            except GameError as error:
                self.panel.mensagem(str(error))
        self._atualizar_lote_preview()

    def on_key_press(self, key, modifiers):
        if isinstance(self.tool, T.LoteTool) and key == arcade.key.R:
            self.ctx.rotacao_lote += math.pi / 12
            self._atualizar_lote_preview()
            return
        if key == arcade.key.C:
            self._selecionar_tool(T.CameraTool(), "camera")
            return
        self.camera.keys.add(key)

    def on_key_release(self, key, modifiers):
        self.camera.keys.discard(key)
