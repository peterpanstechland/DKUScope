#!/usr/bin/env python3
"""Lego 6x6 baseplate procurement hints for the campus physical model.

Automatic pixel classification on the DKU 2023 PDF-style map is unreliable (pastel fills,
tiny legend icons, roofs vs roads). This module uses **curated** per-cell budgets that were
hand-calibrated against:

- ``docs/dku-campus-map-2023.png`` inside ``grid_layout_presets.json`` ``map_roi``
- Twin Profile **B** grid: 8x8 + 8x8 = **128** cells (matches ``project_config.json``)
- Map legend grouping (academic / sports / mixed orange facilities / residential courtyards)
  mapped to the eight ``project_config.json`` ``classes`` (type ids 1..8)

**Always** verify on a printed overlay before purchasing; adjust counts in
``CURATED_COUNTS_B`` if you shift ROI or grid size.

Profile **A** (10x20 = 200 cells) is derived by proportional integer allocation from Profile B.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

# Sum must equal 128 (Profile B twin 8x16 cells).
# Keys: class_id matching project_config.json / hardware color table.
CURATED_COUNTS_B: dict[int, int] = {
    1: 14,  # 教学建筑 -> 红
    2: 8,  # 体育场地 -> 咖啡
    3: 2,  # 餐厅 (CCTW) -> 黄
    4: 8,  # 行政 (ADB, Service 等) -> 黑
    5: 16,  # 生活服务 (宿舍、SSH、CC) -> 粉
    6: 24,  # 绿地 -> 绿
    7: 14,  # 水体 -> 蓝
    8: 42,  # 道路 / 广场浅色铺装 -> 白
}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _scale_counts(src: dict[int, int], target_total: int) -> dict[int, int]:
    s0 = sum(src.values())
    if s0 <= 0:
        raise ValueError("empty source counts")
    raw = [target_total * src[i] / s0 for i in sorted(src)]
    flo = [int(math.floor(x)) for x in raw]
    rem = target_total - sum(flo)
    frac = sorted([(raw[i] - flo[i], i) for i in range(len(flo))], reverse=True)
    for k in range(rem):
        flo[frac[k][1]] += 1
    keys = sorted(src)
    return {keys[i]: flo[i] for i in range(len(keys))}


def main() -> None:
    root = _repo_root()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--redundancy",
        type=float,
        default=0.15,
        help="Extra fraction per class before ceil, e.g. 0.15 => +15%%",
    )
    ap.add_argument(
        "--profile",
        choices=("B", "A"),
        default="B",
        help="B=128 cells (8x16 twin). A=200 cells (10x20 twin), scaled from B.",
    )
    args = ap.parse_args()

    if sum(CURATED_COUNTS_B.values()) != 128:
        raise SystemExit("CURATED_COUNTS_B must sum to 128")

    base = dict(CURATED_COUNTS_B)
    if args.profile == "A":
        base = _scale_counts(CURATED_COUNTS_B, 200)

    proj = json.loads((root / "software/python/config/project_config.json").read_text(encoding="utf-8"))
    classes = {c["class_id"]: c for c in proj["classes"]}
    r = args.redundancy

    total = sum(base.values())
    print(f"Profile {args.profile}: {total} cells (6x6 plates), redundancy +{r*100:.0f}% per class (ceil)\n")
    for cid in range(1, 9):
        c = classes[cid]
        n0 = base[cid]
        n1 = int(math.ceil(n0 * (1.0 + r)))
        ex = c.get("building_examples") or ""
        print(f"{cid}  {c['label']:<8} {c['color_name']:<4}  plan={n0:3d}  +冗余->{n1:3d}  ({ex})")


if __name__ == "__main__":
    main()
