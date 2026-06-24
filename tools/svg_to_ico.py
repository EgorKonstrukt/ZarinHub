"""Convert SVG to multi-size .ico using PyQt6 + Pillow."""
import struct
from pathlib import Path
from io import BytesIO
from PIL import Image

from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtCore import Qt

SIZES = [16, 32, 48, 64, 128, 256]


def _render_pngs(svg_path: str, sizes: list[int]) -> list[Image.Image]:
    renderer = QSvgRenderer(svg_path)
    images = []
    for s in sizes:
        img = QImage(s, s, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        painter = QPainter(img)
        renderer.render(painter)
        painter.end()
        png_tmp = Path.home() / f"_zh_ico_{s}.png"
        if img.save(str(png_tmp), "PNG"):
            data = png_tmp.read_bytes()
            png_tmp.unlink()
            images.append(Image.open(BytesIO(data)))
        else:
            raise RuntimeError(f"Failed to render SVG at {s}x{s}")
    return images


def _images_to_ico(images: list[Image.Image], ico_path: str):
    png_data = []
    for im in images:
        buf = BytesIO()
        im.save(buf, format="PNG")
        png_data.append(buf.getvalue())

    count = len(png_data)
    header_size = 6 + count * 16
    offsets = []
    offset = header_size
    for data in png_data:
        offsets.append(offset)
        offset += len(data)

    with open(ico_path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, count))
        for im, data, off in zip(images, png_data, offsets):
            w = im.width if im.width < 256 else 0
            h = im.height if im.height < 256 else 0
            f.write(struct.pack("<BBBBHHII",
                w if w != 256 else 0,
                h if h != 256 else 0,
                0, 0, 1, 32, len(data), off))
        for data in png_data:
            f.write(data)


def svg_to_ico(svg_path: str, ico_path: str, sizes: list[int] | None = None):
    if sizes is None:
        sizes = SIZES
    images = _render_pngs(svg_path, sizes)
    _images_to_ico(images, ico_path)
    return str(ico_path)


def ensure_ico(svg_path: str | None = None) -> str:
    root = Path(__file__).resolve().parent.parent
    svg = Path(svg_path) if svg_path else root / "zarin_icon.svg"
    ico = root / "zarin_icon.ico"
    if not ico.exists() or (svg.exists() and svg.stat().st_mtime > ico.stat().st_mtime):
        print(f"Converting {svg} -> {ico}")
        svg_to_ico(str(svg), str(ico))
    return str(ico)


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parent.parent
    svg = sys.argv[1] if len(sys.argv) > 1 else str(root / "zarin_icon.svg")
    ico = sys.argv[2] if len(sys.argv) > 2 else str(root / "zarin_icon.ico")
    svg_to_ico(svg, ico)
    print(f"Created: {ico}")
