"""Gera WebP animado do banner VIVE o MOMENTO."""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "web" / "static" / "videos" / "moment-hero-src.jpg"
OUT_WEBP = ROOT / "web" / "static" / "videos" / "moment-banner.webp"
OUT_POSTER = ROOT / "web" / "static" / "videos" / "moment-poster.jpg"

W, H = 720, 200
FRAMES = 36
FPS = 12


def _font(size: int):
    for name in ("arialbd.ttf", "Arial Bold.ttf", "segoeuib.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _crop_zoom(img: Image.Image, zoom: float) -> Image.Image:
    iw, ih = img.size
    zw, zh = int(iw / zoom), int(ih / zoom)
    left = (iw - zw) // 2
    top = max(0, int((ih - zh) * 0.42))
    box = (left, top, left + zw, top + zh)
    return img.crop(box).resize((W, H), Image.Resampling.LANCZOS)


def build(src: Path) -> None:
    base = Image.open(src).convert("RGB")
    font = _font(34)
    frames: list[Image.Image] = []

    for i in range(FRAMES):
        t = i / max(FRAMES - 1, 1)
        zoom = 1.0 + 0.14 * t
        frame = _crop_zoom(base, zoom)

        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for y in range(H):
            alpha = int(120 * (y / H) ** 1.6)
            draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))

        text_alpha = 0
        if t >= 0.45:
            text_alpha = int(255 * min(1.0, (t - 0.45) / 0.35))
        if text_alpha > 0:
            label = "VIVE o MOMENTO!"
            bbox = draw.textbbox((0, 0), label, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            x = (W - tw) // 2
            y = H - th - 18
            glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            gdraw = ImageDraw.Draw(glow)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                gdraw.text((x + dx, y + dy), label, font=font, fill=(0, 0, 0, text_alpha))
            gdraw.text((x, y), label, font=font, fill=(255, 230, 90, text_alpha))
            overlay = Image.alpha_composite(overlay, glow)

        frame = frame.convert("RGBA")
        frame = Image.alpha_composite(frame, overlay)
        frames.append(frame.convert("RGB"))

    OUT_WEBP.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUT_POSTER,
        "JPEG",
        quality=88,
        optimize=True,
    )
    frames[0].save(
        OUT_WEBP,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / FPS),
        loop=0,
        quality=82,
        method=6,
    )
    print(f"OK: {OUT_WEBP} ({len(frames)} frames)")


if __name__ == "__main__":
    if not SRC.exists():
        raise SystemExit(f"Fonte em falta: {SRC}")
    build(SRC)