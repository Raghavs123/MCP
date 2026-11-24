"""Turn reports/demo_output.txt into docs/demo.gif (a ~20-second terminal animation).

    pip install -e ".[demo]"      (Pillow)
    python scripts/make_demo_gif.py

Commands are "typed" letter by letter, outputs appear line by line. The text is the real
saved output of scripts/record_demo.py; the GIF only animates it (not a screen capture).
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WIDTH, HEIGHT, PAD, COLS = 960, 400, 18, 86
BG, FG, CMD, DIM = (24, 26, 33), (220, 223, 228), (126, 231, 135), (139, 148, 158)


def font(size: int = 16):
    for name in ("consola.ttf", "DejaVuSansMono.ttf", "Menlo.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size=size)


def frame(lines: list[tuple[str, tuple]], fnt, line_h: int) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)
    for i, color in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):  # window dots
        d.ellipse((PAD + i * 22, 10, PAD + i * 22 + 12, 22), fill=color)
    visible = lines[-((HEIGHT - 40) // line_h) :]
    for i, (text, color) in enumerate(visible):
        d.text((PAD, 34 + i * line_h), text, font=fnt, fill=color)
    return img


def main() -> int:
    src = ROOT / "reports" / "demo_output.txt"
    raw = src.read_text(encoding="utf-8").splitlines()
    fnt, line_h = font(16), 21
    frames, durations, shown = [], [], []
    for line in raw:
        if line.startswith("$ "):
            for n in range(2, len(line) + 1, 3):  # type the command, 3 letters per frame
                frames.append(frame([*shown, (line[:n] + "_", CMD)], fnt, line_h))
                durations.append(60)
            shown.append((line, CMD))
            frames.append(frame(shown, fnt, line_h))
            durations.append(1300)  # "thinking"
            continue
        for part in textwrap.wrap(line, COLS) or [""]:
            shown.append((part, DIM if part.startswith(("tool", "time")) else FG))
            frames.append(frame(shown, fnt, line_h))
            durations.append(750)
    durations[-1] = 5000  # hold the last frame
    out = ROOT / "docs" / "demo.gif"
    out.parent.mkdir(exist_ok=True)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=durations, loop=0)
    print(f"wrote {out}: {len(frames)} frames, {sum(durations) / 1000:.1f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
