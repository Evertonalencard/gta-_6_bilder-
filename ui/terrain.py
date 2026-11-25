"""Mascara simples de terreno baseada na imagem de mapa usada pela interface."""
import os

from PIL import Image


class ImageTerrain:
    def __init__(self, path):
        self.image = Image.open(path).convert("RGB") if os.path.exists(path) else None
        self.width, self.height = self.image.size if self.image else (1, 1)

    def is_land(self, x, y):
        if not 0 <= x <= 1 or not 0 <= y <= 1:
            return False
        if self.image is None:
            return True
        pixel = self.image.getpixel((
            round(x * (self.width - 1)),
            round(y * (self.height - 1)),
        ))
        red, green, blue = pixel
        water = blue > 80 and blue - red > 25 and blue - green > 10
        return not water
