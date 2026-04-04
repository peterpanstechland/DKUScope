from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Set

from .config_schema import ProjectConfig
from .detection_service import FrameResult, CellResult


@dataclass
class BuildingResult:
    id: str
    class_id: int
    label: str
    cells: List[List[int]]   # [[row, col], ...]
    footprint_w: int
    footprint_h: int
    is_fixed: bool = False


@dataclass
class WorldState:
    seq: int
    timestamp_ms: int
    buildings: List[BuildingResult]
    metrics: Dict[str, float]


def reconstruct_world_state(result: FrameResult, config: ProjectConfig) -> WorldState:
    """
    Convert cell-level frame_state into building-level world_state.

    Steps:
    1. group cells by class_id
    2. run 4-neighborhood connected components
    3. validate each component as a rectangle
    4. validate rectangle size against allowed_footprints
    5. emit buildings + simple metrics
    """

    cells = result.cells
    rows = result.rows
    cols = result.cols

    class_cfg_map = {cls.class_id: cls for cls in config.classes}
    cell_map: Dict[Tuple[int, int], CellResult] = {(c.row, c.col): c for c in cells}

    # -------- metrics --------
    total_cells = rows * cols if rows > 0 and cols > 0 else 1
    known_cells = [c for c in cells if c.class_id != -1]
    green_cells = [c for c in cells if c.class_id == 6]
    water_cells = [c for c in cells if c.class_id == 7]
    road_cells = [c for c in cells if c.class_id == 8]
    built_cells = [c for c in cells if c.class_id not in (-1, 6, 7, 8)]

    metrics = {
        "coverage_ratio": round(len(known_cells) / total_cells, 4),
        "green_ratio": round(len(green_cells) / total_cells, 4),
        "water_ratio": round(len(water_cells) / total_cells, 4),
        "road_ratio": round(len(road_cells) / total_cells, 4),
        "built_ratio": round(len(built_cells) / total_cells, 4),
    }

    # -------- reconstruction --------
    # Group positions by class_id, ignore unknown
    positions_by_class: Dict[int, Set[Tuple[int, int]]] = {}
    for c in cells:
        if c.class_id == -1:
            continue
        positions_by_class.setdefault(c.class_id, set()).add((c.row, c.col))

    buildings: List[BuildingResult] = []
    building_counter = 1

    for class_id, positions in positions_by_class.items():
        cfg = class_cfg_map.get(class_id)
        if cfg is None:
            continue

        allowed = set(cfg.allowed_footprints or ["1x1"])
        visited: Set[Tuple[int, int]] = set()

        for pos in positions:
            if pos in visited:
                continue

            component = _collect_component(start=pos, positions=positions, visited=visited)
            if not component:
                continue

            bbox = _component_bbox(component)
            min_r, max_r, min_c, max_c = bbox
            footprint_h = max_r - min_r + 1
            footprint_w = max_c - min_c + 1

            # Must be a full rectangle in MVP
            if not _is_full_rectangle(component, bbox):
                continue

            fp = f"{footprint_w}x{footprint_h}"
            fp_rot = f"{footprint_h}x{footprint_w}"

            if fp not in allowed and fp_rot not in allowed:
                continue

            ordered_cells = sorted(component)
            buildings.append(
                BuildingResult(
                    id=f"b_{building_counter}",
                    class_id=class_id,
                    label=cfg.label,
                    cells=[[r, c] for r, c in ordered_cells],
                    footprint_w=footprint_w,
                    footprint_h=footprint_h,
                    is_fixed=cfg.is_fixed_default,
                )
            )
            building_counter += 1

    return WorldState(
        seq=result.seq,
        timestamp_ms=result.timestamp_ms,
        buildings=buildings,
        metrics=metrics,
    )


def world_state_to_dict(world: WorldState) -> Dict:
    return {
        "type": "world_state",
        "seq": world.seq,
        "timestamp_ms": world.timestamp_ms,
        "buildings": [asdict(b) for b in world.buildings],
        "metrics": world.metrics,
    }


def _collect_component(
    start: Tuple[int, int],
    positions: Set[Tuple[int, int]],
    visited: Set[Tuple[int, int]],
) -> List[Tuple[int, int]]:
    stack = [start]
    component: List[Tuple[int, int]] = []

    while stack:
        r, c = stack.pop()
        if (r, c) in visited:
            continue
        if (r, c) not in positions:
            continue

        visited.add((r, c))
        component.append((r, c))

        # 4-neighborhood
        neighbors = [
            (r - 1, c),
            (r + 1, c),
            (r, c - 1),
            (r, c + 1),
        ]
        for nb in neighbors:
            if nb not in visited and nb in positions:
                stack.append(nb)

    return component


def _component_bbox(component: List[Tuple[int, int]]) -> Tuple[int, int, int, int]:
    rows = [r for r, _ in component]
    cols = [c for _, c in component]
    return min(rows), max(rows), min(cols), max(cols)


def _is_full_rectangle(
    component: List[Tuple[int, int]],
    bbox: Tuple[int, int, int, int],
) -> bool:
    min_r, max_r, min_c, max_c = bbox
    comp_set = set(component)

    for r in range(min_r, max_r + 1):
        for c in range(min_c, max_c + 1):
            if (r, c) not in comp_set:
                return False
    return True