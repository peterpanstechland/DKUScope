#!/usr/bin/env python3
"""Overlay twin-table logical grids only inside campus-map ROI.

This script renders only the two requested distributions:
- Profile B: 8x16 (two 8x8 tables side-by-side)
- Profile A: 10x20 (two 10x10 tables side-by-side)

``table_gap_cm`` is extra space between the two table outers; 0 means modular abutment
so the seam between active grids equals one internal road width ``g``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class RoiRect:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class TwinLayout:
    table_gap_cm: float
    vertical_shift_cells: float
    horizontal_shift_cells: float


@dataclass(frozen=True)
class Profile:
    key: str
    label_en: str
    module_cells: int
    road_cm: float
    output_suffix: str


@dataclass(frozen=True)
class Presets:
    roi: RoiRect
    cell_size_cm: float
    twin: TwinLayout
    profiles: list[Profile]


def _load_presets(path: Path) -> Presets:
    data = json.loads(path.read_text(encoding="utf-8"))

    roi_cfg = data["map_roi"]
    if roi_cfg.get("mode") != "normalized_rect":
        raise ValueError("map_roi.mode must be 'normalized_rect'")

    roi = RoiRect(
        x=float(roi_cfg["x"]),
        y=float(roi_cfg["y"]),
        w=float(roi_cfg["w"]),
        h=float(roi_cfg["h"]),
    )
    twin_cfg = data["twin_layout"]
    twin = TwinLayout(
        table_gap_cm=float(twin_cfg["table_gap_cm"]),
        vertical_shift_cells=float(twin_cfg.get("vertical_shift_cells", 0.0)),
        horizontal_shift_cells=float(twin_cfg.get("horizontal_shift_cells", 0.0)),
    )

    profiles = [
        Profile(
            key=str(p["key"]),
            label_en=str(p["label_en"]),
            module_cells=int(p["module_cells"]),
            road_cm=float(p["road_cm"]),
            output_suffix=str(p["output_suffix"]),
        )
        for p in data["profiles"]
    ]

    return Presets(
        roi=roi,
        cell_size_cm=float(data["physical"]["cell_size_cm"]),
        twin=twin,
        profiles=profiles,
    )


def _try_font(size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def _caption(img: Image.Image, text: str) -> Image.Image:
    w, h = img.size
    pad = 40
    font = _try_font(20)
    banner = Image.new("RGBA", (w, pad), (20, 20, 24, 235))
    d = ImageDraw.Draw(banner)
    d.text((12, 10), text, fill=(240, 240, 240, 255), font=font)
    out = Image.new("RGBA", (w, h + pad), (0, 0, 0, 255))
    out.paste(img, (0, pad))
    out.paste(banner, (0, 0))
    return out


def _roi_px(base: Image.Image, roi: RoiRect) -> tuple[float, float, float, float]:
    w, h = base.size
    x0 = roi.x * w
    y0 = roi.y * h
    x1 = x0 + roi.w * w
    y1 = y0 + roi.h * h
    return x0, y0, x1, y1


def _table_active_cm(cells: int, s_cm: float, g_cm: float) -> float:
    return cells * s_cm + (cells - 1) * g_cm


def _table_outer_cm(cells: int, s_cm: float, g_cm: float) -> float:
    # Hardware spec convention: b=g/2 on each edge -> L_out = N*(s+g)
    return cells * (s_cm + g_cm)


def _draw_cells(
    draw: ImageDraw.ImageDraw,
    x0: float,
    y0: float,
    *,
    cells: int,
    s_px: float,
    g_px: float,
    line_color: tuple[int, int, int, int],
    outer_color: tuple[int, int, int, int],
) -> None:
    # Draw each cell rectangle; roads remain blank spaces between rectangles.
    for r in range(cells):
        yy = y0 + r * (s_px + g_px)
        for c in range(cells):
            xx = x0 + c * (s_px + g_px)
            # Dark under-stroke + bright stroke makes lines readable on all map colors.
            draw.rectangle((xx, yy, xx + s_px, yy + s_px), outline=(10, 10, 12, 240), width=4)
            draw.rectangle((xx, yy, xx + s_px, yy + s_px), outline=line_color, width=2)

    total = cells * s_px + (cells - 1) * g_px
    draw.rectangle((x0, y0, x0 + total, y0 + total), outline=outer_color, width=3)


def _render_twin_map_only(base: Image.Image, presets: Presets, profile: Profile) -> Image.Image:
    out = base.convert("RGBA")
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    roi_x0, roi_y0, roi_x1, roi_y1 = _roi_px(base, presets.roi)
    roi_w = roi_x1 - roi_x0
    roi_h = roi_y1 - roi_y0

    n = profile.module_cells
    s_cm = presets.cell_size_cm
    g_cm = profile.road_cm
    gap_cm = presets.twin.table_gap_cm

    active_cm = _table_active_cm(n, s_cm, g_cm)
    outer_cm = _table_outer_cm(n, s_cm, g_cm)
    border_cm = g_cm / 2.0
    total_w_cm = outer_cm * 2.0 + gap_cm
    total_h_cm = outer_cm

    scale = min(roi_w / total_w_cm, roi_h / total_h_cm)
    if scale <= 0:
        raise ValueError("Computed scale <= 0. Check map_roi settings.")

    s_px = s_cm * scale
    g_px = g_cm * scale
    gap_px = gap_cm * scale
    active_px = active_cm * scale
    outer_px = outer_cm * scale
    border_px = border_cm * scale

    used_w = total_w_cm * scale
    used_h = total_h_cm * scale
    start_x = roi_x0 + (roi_w - used_w) / 2.0
    start_y = roi_y0 + (roi_h - used_h) / 2.0
    start_x += presets.twin.horizontal_shift_cells * (s_px + g_px)
    # Positive value moves overlay upward by N cell pitches.
    start_y -= presets.twin.vertical_shift_cells * (s_px + g_px)
    min_x = roi_x0
    max_x = roi_x1 - used_w
    if start_x < min_x:
        start_x = min_x
    if start_x > max_x:
        start_x = max_x
    min_y = roi_y0
    max_y = roi_y1 - used_h
    if start_y < min_y:
        start_y = min_y
    if start_y > max_y:
        start_y = max_y

    left_x = start_x
    right_x = start_x + outer_px + gap_px

    # Visual guide: map-only ROI boundary.
    draw.rectangle((roi_x0, roi_y0, roi_x1, roi_y1), outline=(0, 200, 255, 160), width=2)

    # Table outer apertures (gold), then active cells are inset by half-road borders.
    draw.rectangle((left_x, start_y, left_x + outer_px, start_y + outer_px), outline=(255, 215, 0, 220), width=3)
    draw.rectangle((right_x, start_y, right_x + outer_px, start_y + outer_px), outline=(255, 215, 0, 220), width=3)

    _draw_cells(
        draw,
        left_x + border_px,
        start_y + border_px,
        cells=n,
        s_px=s_px,
        g_px=g_px,
        line_color=(60, 245, 255, 235),
        outer_color=(255, 215, 0, 0),
    )
    _draw_cells(
        draw,
        right_x + border_px,
        start_y + border_px,
        cells=n,
        s_px=s_px,
        g_px=g_px,
        line_color=(60, 245, 255, 235),
        outer_color=(255, 215, 0, 0),
    )

    # Red middle gap strip between two tables.
    draw.rectangle(
        (left_x + outer_px, start_y, right_x, start_y + outer_px),
        outline=(255, 80, 80, 230),
        width=3,
    )

    merged = Image.alpha_composite(out, layer)
    rows = n
    cols = n * 2
    caption = (
        f"{profile.key}: twin map-only {rows}x{cols} | s={s_cm:.2f}cm g={g_cm:.2f}cm "
        f"b={border_cm:.2f}cm table_gap={gap_cm:.2f}cm | physical-gap={gap_px:.1f}px | "
        f"shift=(right {presets.twin.horizontal_shift_cells:.1f}, up {presets.twin.vertical_shift_cells:.1f}) cells"
    )
    return _caption(merged, caption)


def main() -> None:
    root = _repo_root()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--presets",
        type=Path,
        default=root / "software" / "python" / "config" / "grid_layout_presets.json",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=root / "docs" / "dku-campus-map-2023.png",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=root / "docs",
    )
    args = parser.parse_args()

    presets = _load_presets(args.presets)
    base = Image.open(args.input).convert("RGBA")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for profile in presets.profiles:
        img = _render_twin_map_only(base, presets, profile)
        out = args.out_dir / f"{args.input.stem}-grid-{profile.key}-twin-map-only-{profile.output_suffix}.png"
        img.save(out)
        print("Wrote:", out)


if __name__ == "__main__":
    main()
