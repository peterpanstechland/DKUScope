from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30


@dataclass
class GridConfig:
    # Default: twin Profile B (two 8x8), g=s=4.9cm, b=g/2 — see docs/hardware-spec.md & grid_layout_presets.json
    rows: int = 8
    cols: int = 16
    cell_gap_mm: float = 49.0
    border_mm: float = 24.5


@dataclass
class BlockConfig:
    block_studs_w: int = 6
    block_studs_h: int = 6
    block_size_cm: float = 4.8
    plate_studs_w: int = 6
    plate_studs_h: int = 6
    plate_size_cm: float = 4.8


@dataclass
class CalibrationConfig:
    enabled: bool = False
    source_points: List[List[float]] = field(default_factory=list)
    destination_points: List[List[float]] = field(default_factory=list)
    output_width: int = 640
    output_height: int = 480


@dataclass
class ProjectionCalibrationConfig:
    """Projection mapping calibration from top camera."""
    enabled: bool = False
    projector_camera_index: int = 1
    projector_width: int = 1920
    projector_height: int = 1080
    pattern_cols: int = 9
    pattern_rows: int = 6
    source_points: List[List[float]] = field(default_factory=list)
    destination_points: List[List[float]] = field(default_factory=list)
    warp_matrix: List[List[float]] = field(default_factory=list)


@dataclass
class TableUnitConfig:
    """One physical table module in a multi-table layout."""
    unit_id: str = "A"
    camera_index: int = 0
    grid_row_offset: int = 0
    grid_col_offset: int = 0
    grid_rows: int = 8
    grid_cols: int = 8
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)


@dataclass
class LayoutConfig:
    """Describes how multiple table units are arranged."""
    enabled: bool = False
    layout_rows: int = 1
    layout_cols: int = 1
    units: List["TableUnitConfig"] = field(default_factory=list)


@dataclass
class BuildingClassConfig:
    class_id: int
    label: str
    label_en: str = ""
    color_name: str = ""
    color_name_en: str = ""
    color_hex: str = ""
    building_examples: str = ""
    building_examples_en: str = ""
    is_fixed_default: bool = False
    allowed_footprints: List[str] = field(default_factory=lambda: ["1x1"])
    calibrated_lab: List[float] = field(default_factory=list)


@dataclass
class ProjectConfig:
    camera: CameraConfig = field(default_factory=CameraConfig)
    grid: GridConfig = field(default_factory=GridConfig)
    block: BlockConfig = field(default_factory=BlockConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    projection: ProjectionCalibrationConfig = field(default_factory=ProjectionCalibrationConfig)
    layout: LayoutConfig = field(default_factory=LayoutConfig)
    classes: List[BuildingClassConfig] = field(
        default_factory=lambda: [
            BuildingClassConfig(
                class_id=1, label="教学建筑", label_en="Academic",
                color_name="红色", color_name_en="Red", color_hex="#D73A49",
                building_examples="AB, 图书馆, IB", building_examples_en="AB, Library, IB",
                allowed_footprints=["1x1", "2x2", "3x2"],
            ),
            BuildingClassConfig(
                class_id=2, label="体育场地", label_en="Sports",
                color_name="咖啡色", color_name_en="Brown", color_hex="#8B5A2B",
                building_examples="室外体育场, 体育馆", building_examples_en="Outdoor Field, Gym",
                allowed_footprints=["1x1", "2x2"],
            ),
            BuildingClassConfig(
                class_id=3, label="餐厅建筑", label_en="Dining",
                color_name="黄色", color_name_en="Yellow", color_hex="#F2CC0C",
                building_examples="CCTW", building_examples_en="CCTW",
                allowed_footprints=["1x1", "2x1"],
            ),
            BuildingClassConfig(
                class_id=4, label="行政建筑", label_en="Administrative",
                color_name="黑色", color_name_en="Black", color_hex="#2F2F2F",
                building_examples="ADB, Service Building", building_examples_en="ADB, Service Building",
                allowed_footprints=["1x1", "2x1"],
            ),
            BuildingClassConfig(
                class_id=5, label="生活服务", label_en="Residential",
                color_name="粉色", color_name_en="Pink", color_hex="#F7A1C4",
                building_examples="宿舍, SSH, CC", building_examples_en="Dorm, SSH, CC",
                allowed_footprints=["1x1", "2x2"],
            ),
            BuildingClassConfig(
                class_id=6, label="绿地", label_en="Green Space",
                color_name="绿色", color_name_en="Green", color_hex="#2EA043",
                building_examples_en="",
                allowed_footprints=["1x1", "2x2", "3x3"],
            ),
            BuildingClassConfig(
                class_id=7, label="水体", label_en="Water",
                color_name="蓝色", color_name_en="Blue", color_hex="#1F6FEB",
                building_examples_en="",
                allowed_footprints=["1x1", "2x2", "2x3", "3x3"],
            ),
            BuildingClassConfig(
                class_id=8, label="默认道路", label_en="Road",
                color_name="白色", color_name_en="White", color_hex="#F5F5F5",
                building_examples_en="",
                allowed_footprints=["1x1"],
            ),
        ]
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProjectConfig":
        camera = CameraConfig(**data.get("camera", {}))
        grid = GridConfig(**data.get("grid", {}))
        block = BlockConfig(**data.get("block", {}))
        calibration = CalibrationConfig(**data.get("calibration", {}))
        projection = ProjectionCalibrationConfig(**data.get("projection", {}))

        layout_raw = data.get("layout", {})
        layout_units = [
            TableUnitConfig(
                **{
                    k: (CalibrationConfig(**v) if k == "calibration" else v)
                    for k, v in u.items()
                }
            )
            for u in layout_raw.get("units", [])
        ]
        layout = LayoutConfig(
            enabled=layout_raw.get("enabled", False),
            layout_rows=layout_raw.get("layout_rows", 1),
            layout_cols=layout_raw.get("layout_cols", 1),
            units=layout_units,
        )

        classes = [
            BuildingClassConfig(**item) for item in data.get("classes", [])
        ] or cls().classes
        return cls(
            camera=camera,
            grid=grid,
            block=block,
            calibration=calibration,
            projection=projection,
            layout=layout,
            classes=classes,
        )

