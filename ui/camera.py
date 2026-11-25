import arcade

ZOOM_MIN, ZOOM_MAX = 0.4, 40.0


class CameraController:
    """Pan (arrastar com botao direito/meio ou WASD/setas) e zoom (roda do mouse) centrado no cursor."""

    def __init__(self, window, largura_mundo, altura_mundo):
        self.cam = arcade.Camera2D()
        self.limites = (largura_mundo, altura_mundo)
        self.cam.position = (largura_mundo / 2, altura_mundo / 2)
        self.keys = set()

    def focar(self, wx, wy, zoom):
        self.cam.position = (wx, wy)
        self.cam.zoom = zoom

    def resize(self):
        self.cam.match_window()

    def arrastar(self, dx, dy):
        x, y = self.cam.position
        self.cam.position = (x - dx / self.cam.zoom, y - dy / self.cam.zoom)

    def zoom_em(self, sx, sy, fator):
        antes = self.cam.unproject((sx, sy))
        self.cam.zoom = max(ZOOM_MIN, min(ZOOM_MAX, self.cam.zoom * fator))
        depois = self.cam.unproject((sx, sy))
        x, y = self.cam.position
        self.cam.position = (x + antes[0] - depois[0], y + antes[1] - depois[1])

    def update(self, dt):
        v = 600 * dt / self.cam.zoom
        dx = (arcade.key.D in self.keys or arcade.key.RIGHT in self.keys) - (arcade.key.A in self.keys or arcade.key.LEFT in self.keys)
        dy = (arcade.key.W in self.keys or arcade.key.UP in self.keys) - (arcade.key.S in self.keys or arcade.key.DOWN in self.keys)
        if dx or dy:
            x, y = self.cam.position
            self.cam.position = (x + dx * v, y + dy * v)

    def to_world(self, sx, sy):
        p = self.cam.unproject((sx, sy))
        return p[0], p[1]

    def use(self):
        self.cam.use()
