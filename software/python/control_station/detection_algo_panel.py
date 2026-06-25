from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

import cv2
import numpy as np

from .background_refs import (
    capture_background_from_lab_grid,
    load_background_refs,
    save_background_refs,
)
from .cell_analysis import preprocess_frame
from .config_schema import DetectionConfig, ProjectConfig, TableUnitConfig
from .detection_service import GridDetector, open_camera
from .i18n import t
from .log_service import get_logger

logger = get_logger("detection")


class DetectionAlgoPanel(ttk.LabelFrame):
    """Detection algorithm settings and empty-table background capture."""

    def __init__(
        self,
        parent: tk.Widget,
        get_config: Callable[[], ProjectConfig],
        on_apply: Callable[[ProjectConfig], None],
        **kwargs,
    ) -> None:
        super().__init__(parent, text=t("sect_detection_algo"), padding=8, **kwargs)
        self._get_config = get_config
        self._on_apply = on_apply
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(1, weight=1)

        self.enabled_var = tk.BooleanVar(value=True)
        self.clahe_var = tk.BooleanVar(value=True)
        self.glare_var = tk.BooleanVar(value=True)
        self.debug_var = tk.BooleanVar(value=False)

        row = 0
        for var, key in (
            (self.enabled_var, "chk_det_enabled"),
            (self.clahe_var, "chk_det_clahe"),
            (self.glare_var, "chk_det_glare"),
            (self.debug_var, "chk_det_debug"),
        ):
            ttk.Checkbutton(self, text=t(key), variable=var).grid(
                row=row, column=0, columnspan=2, sticky="w", pady=2,
            )
            row += 1

        self.confidence_var = tk.StringVar(value="40")
        self.bg_delta_var = tk.StringVar(value="18")
        self.min_area_var = tk.StringVar(value="0.12")
        self.glare_l_var = tk.StringVar(value="245")
        self.l_pad_var = tk.StringVar(value="8")
        self.ab_pad_var = tk.StringVar(value="12")
        self.unit_var = tk.StringVar(value="global")

        fields = [
            ("lbl_det_confidence", self.confidence_var),
            ("lbl_det_bg_delta", self.bg_delta_var),
            ("lbl_det_min_area", self.min_area_var),
            ("lbl_det_glare_l", self.glare_l_var),
            ("lbl_det_l_pad", self.l_pad_var),
            ("lbl_det_ab_pad", self.ab_pad_var),
        ]
        for label_key, var in fields:
            ttk.Label(self, text=t(label_key)).grid(row=row, column=0, sticky="w", pady=2)
            ttk.Entry(self, textvariable=var, width=10).grid(row=row, column=1, sticky="w", pady=2)
            row += 1

        ttk.Label(self, text=t("lbl_bg_ref_unit")).grid(row=row, column=0, sticky="w", pady=2)
        self.unit_combo = ttk.Combobox(self, textvariable=self.unit_var, width=12, state="readonly")
        self.unit_combo.grid(row=row, column=1, sticky="w", pady=2)
        row += 1

        btn_row = ttk.Frame(self)
        btn_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(btn_row, text=t("btn_capture_bg"), command=self._capture_background).pack(
            side=tk.LEFT, padx=(0, 4),
        )
        ttk.Button(btn_row, text=t("btn_clear_bg"), command=self._clear_background).pack(
            side=tk.LEFT, padx=(0, 4),
        )
        ttk.Button(btn_row, text=t("btn_apply_detection"), command=self._apply).pack(
            side=tk.LEFT, padx=(0, 4),
        )
        row += 1

        self.bg_status_var = tk.StringVar(value=t("bg_ref_none"))
        ttk.Label(self, textvariable=self.bg_status_var, wraplength=360, foreground="#555").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(6, 0),
        )
        row += 1

        ttk.Label(self, text=t("det_algo_hint"), wraplength=360, foreground="#555").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 0),
        )

    def load_from_config(self, config: ProjectConfig) -> None:
        det = config.detection
        self.enabled_var.set(det.enabled)
        self.clahe_var.set(det.use_clahe)
        self.glare_var.set(det.glare_filter_enabled)
        self.debug_var.set(det.debug_overlay)
        self.confidence_var.set(str(det.confidence_threshold))
        self.bg_delta_var.set(str(det.background_delta_threshold))
        self.min_area_var.set(str(det.min_block_area_ratio))
        self.glare_l_var.set(str(det.glare_l_threshold))
        self.l_pad_var.set(str(det.color_range_l_padding))
        self.ab_pad_var.set(str(det.color_range_ab_padding))

        units = ["global"]
        if config.layout.enabled and config.layout.units:
            units.extend(u.unit_id for u in config.layout.units)
        self.unit_combo["values"] = units
        if self.unit_var.get() not in units:
            self.unit_var.set(units[0])
        self._refresh_bg_status()

    def _detection_from_form(self) -> DetectionConfig:
        return DetectionConfig(
            enabled=self.enabled_var.get(),
            use_clahe=self.clahe_var.get(),
            glare_filter_enabled=self.glare_var.get(),
            debug_overlay=self.debug_var.get(),
            confidence_threshold=float(self.confidence_var.get()),
            background_delta_threshold=float(self.bg_delta_var.get()),
            min_block_area_ratio=float(self.min_area_var.get()),
            glare_l_threshold=float(self.glare_l_var.get()),
            color_range_l_padding=float(self.l_pad_var.get()),
            color_range_ab_padding=float(self.ab_pad_var.get()),
        )

    def _apply(self) -> None:
        try:
            config = self._get_config()
            config.detection = self._detection_from_form()
            self._on_apply(config)
            messagebox.showinfo(t("btn_apply_detection"), t("detection_config_saved"))
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num_fmt"))

    def _refresh_bg_status(self) -> None:
        refs = load_background_refs()
        key = self.unit_var.get()
        ref = refs.get(key)
        if ref and ref.rows > 0:
            self.bg_status_var.set(t("bg_ref_ok_fmt", unit=key, rows=ref.rows, cols=ref.cols))
        else:
            self.bg_status_var.set(t("bg_ref_none_fmt", unit=key))

    def _resolve_unit(self, config: ProjectConfig) -> tuple[str, Optional[TableUnitConfig]]:
        key = self.unit_var.get()
        if key == "global":
            return "global", None
        for unit in config.layout.units:
            if unit.unit_id == key:
                return unit.unit_id, unit
        return key, None

    def _capture_background(self) -> None:
        config = self._get_config()
        config.detection = self._detection_from_form()
        unit_key, unit = self._resolve_unit(config)

        try:
            if unit is not None:
                cap = cv2.VideoCapture(unit.camera_index, cv2.CAP_DSHOW)
                rows, cols = unit.grid_rows, unit.grid_cols
                cal = unit.calibration
            else:
                cap = open_camera(config)
                rows, cols = config.grid.rows, config.grid.cols
                cal = config.calibration

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.camera.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.camera.height)
            ok, frame = cap.read()
            cap.release()
            if not ok:
                messagebox.showerror(t("btn_capture_bg"), t("bg_capture_fail"))
                return

            if cal.enabled and len(cal.source_points) == 4:
                src = np.array(cal.source_points, dtype=np.float32)
                dst = np.array(cal.destination_points, dtype=np.float32)
                matrix = cv2.getPerspectiveTransform(src, dst)
                frame = cv2.warpPerspective(frame, matrix, (cal.output_width, cal.output_height))

            if config.detection.use_clahe:
                frame = preprocess_frame(frame, config.detection)
            lab = cv2.cvtColor(frame, cv2.COLOR_BGR2Lab)
            ref = capture_background_from_lab_grid(
                lab, rows, cols, margin_ratio=config.detection.margin_ratio,
            )

            refs = load_background_refs()
            refs[unit_key] = ref
            save_background_refs(refs)
            logger.info("Background ref captured unit=%s rows=%d cols=%d", unit_key, rows, cols)
            self._refresh_bg_status()
            messagebox.showinfo(t("btn_capture_bg"), t("bg_capture_ok_fmt", unit=unit_key))
        except Exception as exc:
            logger.exception("Background capture failed")
            messagebox.showerror(t("btn_capture_bg"), str(exc))

    def _clear_background(self) -> None:
        key = self.unit_var.get()
        if not messagebox.askyesno(t("btn_clear_bg"), t("bg_clear_confirm_fmt", unit=key)):
            return
        refs = load_background_refs()
        refs.pop(key, None)
        save_background_refs(refs)
        logger.info("Background ref cleared unit=%s", key)
        self._refresh_bg_status()
