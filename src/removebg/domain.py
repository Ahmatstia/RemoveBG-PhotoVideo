from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class VideoInfo:
    width: int
    height: int
    duration: float
    rate: Fraction
    frames: int
    has_audio: bool


class Cancelled(Exception):
    pass


def validate_points(points, width, height):
    if not points or not any(p[2] == 1 for p in points):
        raise ValueError("Klik minimal satu titik 'Pertahankan' pada objek.")
    for x, y, label in points:
        if not (0 <= x < width and 0 <= y < height and label in (0, 1)):
            raise ValueError("Titik pilihan di luar gambar. Muat ulang frame pertama.")
