import argparse
import os

import arcade

from bootstrap import build_controller
from ui.game_view import GameView
from ui.terrain import ImageTerrain


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapa", default="assets/leonida_base.jpg", help="imagem base do mapa")
    ap.add_argument("--grafo", default=None, help="JSON salvo pelo botao 'Salvar mapa'")
    ap.add_argument("--dfs", action="store_true", help="Ford-Fulkerson com DFS (padrao: BFS/Edmonds-Karp)")
    a = ap.parse_args()
    terrain = ImageTerrain(a.mapa)
    ctrl = build_controller(
        a.grafo if a.grafo and os.path.exists(a.grafo) else None,
        usar_dfs=a.dfs,
        terrain_validator=terrain.is_land,
        map_size=(terrain.width, terrain.height),
    )
    win = arcade.Window(1400, 900, "Traffic Planning - Leonida", resizable=True)
    win.show_view(GameView(ctrl, a.mapa))
    arcade.run()


if __name__ == "__main__":
    main()
