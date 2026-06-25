from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional

from .calibration_service import run_four_point_calibration
from .camera_preview import CameraPreviewWidget
from .config_schema import CalibrationConfig, TableUnitConfig
from .i18n import t


class CameraUnitCard(ttk.LabelFrame):
    """One camera: preview + device, table position, detection range, calibration."""

    def __init__(
        self,
        parent: tk.Widget,
        unit_id: str,
        camera_values: List[str],
        global_width: int,
        global_height: int,
        global_fps: int,
        total_grid_rows: int,
        total_grid_cols: int,
        layout_rows: int,
        layout_cols: int,
        on_change: Callable[[], None],
        on_remove: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(parent, text=t("cam_card_title", uid=unit_id), padding=8, **kwargs)
        self.unit_id = unit_id
        self._on_change = on_change
        self._global_width = global_width
        self._global_height = global_height
        self._global_fps = global_fps
        self._total_grid_rows = total_grid_rows
        self._total_grid_cols = total_grid_cols
        self._layout_rows = layout_rows
        self._layout_cols = layout_cols
        self._calibration = CalibrationConfig()

        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(1, weight=1)

        self.preview = CameraPreviewWidget(body, preview_width=320, preview_height=240)
        self.preview.grid(row=0, column=0, rowspan=6, sticky="nw", padx=(0, 10))
        self.preview.configure_camera(0, global_width, global_height, global_fps)
        self.preview.set_start_callback(self._sync_preview)

        self.grid_overlay_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            body, text=t("chk_grid_overlay"), variable=self.grid_overlay_var,
            command=self._sync_preview,
        ).grid(row=0, column=1, sticky="w")

        ttk.Label(body, text=t("lbl_camera")).grid(row=1, column=1, sticky="w", pady=(4, 0))
        self.camera_var = tk.StringVar(value=camera_values[0] if camera_values else "0")
        self.camera_combo = ttk.Combobox(
            body, textvariable=self.camera_var, values=camera_values or ["0"],
            state="readonly", width=8,
        )
        self.camera_combo.grid(row=1, column=2, sticky="w", pady=(4, 0))
        self.camera_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_field_change())

        ttk.Label(body, text=t("lbl_table_position")).grid(row=2, column=1, sticky="w", pady=(6, 0))
        self.position_var = tk.StringVar()
        self.position_combo = ttk.Combobox(
            body, textvariable=self.position_var, values=self._position_labels(),
            state="readonly", width=14,
        )
        self.position_combo.grid(row=2, column=2, sticky="w", pady=(6, 0))
        self.position_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_position_change())

        ttk.Label(body, text=t("lbl_detect_range")).grid(row=3, column=1, sticky="w", pady=(6, 0))
        range_frame = ttk.Frame(body)
        range_frame.grid(row=3, column=2, sticky="w", pady=(6, 0))
        self.range_rows_var = tk.StringVar()
        self.range_cols_var = tk.StringVar()
        ttk.Entry(range_frame, textvariable=self.range_rows_var, width=4).pack(side=tk.LEFT)
        ttk.Label(range_frame, text="×").pack(side=tk.LEFT, padx=2)
        ttk.Entry(range_frame, textvariable=self.range_cols_var, width=4).pack(side=tk.LEFT)
        ttk.Label(range_frame, text=t("lbl_grid_cells")).pack(side=tk.LEFT, padx=(4, 0))

        offset_frame = ttk.Frame(body)
        offset_frame.grid(row=4, column=1, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Label(offset_frame, text=t("lbl_grid_offset")).pack(side=tk.LEFT)
        self.row_off_var = tk.StringVar()
        self.col_off_var = tk.StringVar()
        ttk.Entry(offset_frame, textvariable=self.row_off_var, width=4, state="readonly").pack(side=tk.LEFT, padx=(4, 2))
        ttk.Label(offset_frame, text=",").pack(side=tk.LEFT)
        ttk.Entry(offset_frame, textvariable=self.col_off_var, width=4, state="readonly").pack(side=tk.LEFT, padx=(2, 0))

        status_row = ttk.Frame(body)
        status_row.grid(row=5, column=1, columnspan=2, sticky="ew", pady=(8, 0))
        self.calib_status_var = tk.StringVar(value=t("not_calibrated"))
        ttk.Label(status_row, textvariable=self.calib_status_var).pack(side=tk.LEFT)
        ttk.Button(status_row, text=t("btn_calibrate_unit"), command=self._run_calibration).pack(side=tk.LEFT, padx=(8, 0))
        self._remove_btn = ttk.Button(status_row, text=t("btn_remove_camera"), command=self._request_remove)
        self._remove_btn.pack(side=tk.RIGHT)
        self._remove_handler: Optional[Callable[[], None]] = on_remove

        self.range_rows_var.trace_add("write", lambda *_: self._on_field_change())
        self.range_cols_var.trace_add("write", lambda *_: self._on_field_change())

    def _position_labels(self) -> List[str]:
        labels: List[str] = []
        for r in range(self._layout_rows):
            for c in range(self._layout_cols):
                labels.append(self._slot_label(r, c))
        return labels

    def _slot_label(self, slot_row: int, slot_col: int) -> str:
        key = self._position_key(slot_row, slot_col)
        if key == "pos_slot_fmt":
            return t(key, row=slot_row + 1, col=slot_col + 1)
        return t(key)

    def _position_key(self, slot_row: int, slot_col: int) -> str:
        keys = [
            ["pos_tl", "pos_tr"],
            ["pos_bl", "pos_br"],
        ]
        if self._layout_rows == 1 and self._layout_cols == 1:
            return "pos_single"
        if slot_row == 0 and slot_col == 0:
            return "pos_tl"
        if slot_row == 0 and slot_col == self._layout_cols - 1:
            return "pos_tr"
        if slot_row == self._layout_rows - 1 and slot_col == 0:
            return "pos_bl"
        if slot_row == self._layout_rows - 1 and slot_col == self._layout_cols - 1:
            return "pos_br"
        return "pos_slot_fmt"

    def _slot_from_label(self, label: str) -> tuple[int, int]:
        for r in range(self._layout_rows):
            for c in range(self._layout_cols):
                if self._slot_label(r, c) == label:
                    return r, c
        return 0, 0

    def _default_sub_grid(self) -> tuple[int, int]:
        sub_r = max(1, self._total_grid_rows // max(1, self._layout_rows))
        sub_c = max(1, self._total_grid_cols // max(1, self._layout_cols))
        return sub_r, sub_c

    def _apply_position_offsets(self) -> None:
        slot_r, slot_c = self._slot_from_label(self.position_var.get())
        sub_r, sub_c = self._default_sub_grid()
        try:
            sub_r = int(self.range_rows_var.get()) or sub_r
            sub_c = int(self.range_cols_var.get()) or sub_c
        except ValueError:
            pass
        self.row_off_var.set(str(slot_r * sub_r))
        self.col_off_var.set(str(slot_c * sub_c))

    def _on_position_change(self) -> None:
        sub_r, sub_c = self._default_sub_grid()
        self.range_rows_var.set(str(sub_r))
        self.range_cols_var.set(str(sub_c))
        self._apply_position_offsets()
        self._sync_preview()
        self._on_change()

    def _on_field_change(self) -> None:
        self._apply_position_offsets()
        self._on_change()

    def _sync_preview(self) -> None:
        try:
            idx = int(self.camera_var.get())
            sub_r = int(self.range_rows_var.get())
            sub_c = int(self.range_cols_var.get())
        except ValueError:
            return
        self.preview.configure_camera(idx, self._global_width, self._global_height, self._global_fps)
        self.preview.configure_grid_overlay(self.grid_overlay_var.get(), sub_r, sub_c)

    def _run_calibration(self) -> None:
        try:
            idx = int(self.camera_var.get())
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num"))
            return
        messagebox.showinfo(t("dlg_calib_hint_title"), t("dlg_calib_hint"))
        result = run_four_point_calibration(
            idx, self._global_width, self._global_height, self._global_fps,
            grid_rows=int(self.range_rows_var.get() or 2),
            grid_cols=int(self.range_cols_var.get() or 4),
        )
        if result is None:
            messagebox.showwarning(t("dlg_calib_result"), t("dlg_calib_fail"))
            return
        self._calibration = CalibrationConfig(
            enabled=True,
            source_points=result.source_points,
            destination_points=result.destination_points,
            output_width=result.output_width,
            output_height=result.output_height,
        )
        self._refresh_calib_status()
        self._on_change()
        messagebox.showinfo(t("dlg_calib_result"), t("calib_saved_unit", uid=self.unit_id))

    def _request_remove(self) -> None:
        if self._remove_handler:
            self._remove_handler()

    def set_remove_handler(self, handler: Callable[[], None]) -> None:
        self._remove_handler = handler

    def _refresh_calib_status(self) -> None:
        c = self._calibration
        if c.enabled and len(c.source_points) == 4:
            self.calib_status_var.set(t("calibrated_fmt", w=c.output_width, h=c.output_height))
        else:
            self.calib_status_var.set(t("not_calibrated"))

    def set_camera_values(self, values: List[str]) -> None:
        self.camera_combo["values"] = values or ["0"]
        if self.camera_var.get() not in self.camera_combo["values"]:
            self.camera_var.set(self.camera_combo["values"][0])

    def update_layout_context(
        self,
        total_grid_rows: int,
        total_grid_cols: int,
        layout_rows: int,
        layout_cols: int,
        global_width: int,
        global_height: int,
        global_fps: int,
    ) -> None:
        self._total_grid_rows = total_grid_rows
        self._total_grid_cols = total_grid_cols
        self._layout_rows = layout_rows
        self._layout_cols = layout_cols
        self._global_width = global_width
        self._global_height = global_height
        self._global_fps = global_fps
        labels = self._position_labels()
        self.position_combo["values"] = labels
        if self.position_var.get() not in labels and labels:
            self.position_var.set(labels[0])
        self._apply_position_offsets()
        self._sync_preview()

    def load_from_unit(self, unit: TableUnitConfig, index: int) -> None:
        self.unit_id = unit.unit_id
        self.configure(text=t("cam_card_title", uid=unit.unit_id))
        self.camera_var.set(str(unit.camera_index))
        self.range_rows_var.set(str(unit.grid_rows))
        self.range_cols_var.set(str(unit.grid_cols))
        self.row_off_var.set(str(unit.grid_row_offset))
        self.col_off_var.set(str(unit.grid_col_offset))
        self._calibration = unit.calibration
        self._refresh_calib_status()

        labels = self._position_labels()
        matched = labels[0] if labels else ""
        sub_r, sub_c = self._default_sub_grid()
        for slot_r in range(self._layout_rows):
            for slot_c in range(self._layout_cols):
                if unit.grid_row_offset == slot_r * sub_r and unit.grid_col_offset == slot_c * sub_c:
                    matched = self._slot_label(slot_r, slot_c)
                    break
        self.position_var.set(matched)
        self._sync_preview()

    def to_unit_config(self) -> TableUnitConfig:
        return TableUnitConfig(
            unit_id=self.unit_id,
            camera_index=int(self.camera_var.get()),
            grid_row_offset=int(self.row_off_var.get()),
            grid_col_offset=int(self.col_off_var.get()),
            grid_rows=int(self.range_rows_var.get()),
            grid_cols=int(self.range_cols_var.get()),
            calibration=self._calibration,
        )

    def stop_preview(self) -> None:
        self.preview.stop()


class CameraCalibrationTab(ttk.Frame):
    """Dedicated tab: manage camera count, per-camera preview and calibration."""

    def __init__(self, parent: tk.Widget, get_global_camera_settings: Callable[[], tuple[int, int, int]], get_grid_size: Callable[[], tuple[int, int]], **kwargs) -> None:
        super().__init__(parent, padding=12, **kwargs)
        self._get_global_camera_settings = get_global_camera_settings
        self._get_grid_size = get_grid_size
        self._camera_values: List[str] = ["0"]
        self._cards: List[CameraUnitCard] = []
        self._build_ui()

    def _build_ui(self) -> None:
        toolbar = ttk.LabelFrame(self, text=t("sect_cam_setup"), padding=8)
        toolbar.pack(fill=tk.X, pady=(0, 8))

        row1 = ttk.Frame(toolbar)
        row1.pack(fill=tk.X)
        ttk.Label(row1, text=t("lbl_camera_count")).pack(side=tk.LEFT)
        self.count_var = tk.StringVar(value="4")
        count_spin = ttk.Spinbox(row1, from_=1, to=8, textvariable=self.count_var, width=4)
        count_spin.pack(side=tk.LEFT, padx=(4, 8))
        ttk.Button(row1, text=t("btn_apply_count"), command=self._apply_camera_count).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row1, text=t("btn_refresh"), command=self._refresh_camera_list).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row1, text=t("btn_stop_all_previews"), command=self.stop_all_previews).pack(side=tk.LEFT)

        row2 = ttk.Frame(toolbar)
        row2.pack(fill=tk.X, pady=(8, 0))
        self.multi_enable_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text=t("chk_multi_camera"), variable=self.multi_enable_var).pack(side=tk.LEFT)
        ttk.Label(row2, text=t("lbl_cam_layout")).pack(side=tk.LEFT, padx=(16, 4))
        self.layout_rows_var = tk.StringVar(value="2")
        self.layout_cols_var = tk.StringVar(value="2")
        ttk.Entry(row2, textvariable=self.layout_rows_var, width=3).pack(side=tk.LEFT)
        ttk.Label(row2, text="×").pack(side=tk.LEFT, padx=2)
        ttk.Entry(row2, textvariable=self.layout_cols_var, width=3).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(row2, text=t("btn_apply_layout"), command=self._apply_layout_shape).pack(side=tk.LEFT)

        ttk.Label(self, text=t("cam_tab_hint"), wraplength=900, foreground="#555").pack(anchor="w", pady=(0, 8))

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        self._canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self._canvas.yview)
        self._cards_frame = ttk.Frame(self._canvas)
        self._cards_frame.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )
        self._canvas.create_window((0, 0), window=self._cards_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _layout_dims(self) -> tuple[int, int]:
        try:
            lr = max(1, int(self.layout_rows_var.get()))
            lc = max(1, int(self.layout_cols_var.get()))
        except ValueError:
            lr, lc = 2, 2
        return lr, lc

    def _card_context(self) -> dict:
        w, h, fps = self._get_global_camera_settings()
        grid_r, grid_c = self._get_grid_size()
        lr, lc = self._layout_dims()
        return {
            "global_width": w,
            "global_height": h,
            "global_fps": fps,
            "total_grid_rows": grid_r,
            "total_grid_cols": grid_c,
            "layout_rows": lr,
            "layout_cols": lc,
        }

    def _refresh_camera_list(self) -> None:
        from .camera_service import enumerate_cameras
        cams = enumerate_cameras()
        self._camera_values = [str(c.index) for c in cams] or ["0"]
        for card in self._cards:
            card.set_camera_values(self._camera_values)

    def set_camera_values(self, values: List[str]) -> None:
        self._camera_values = values or ["0"]
        for card in self._cards:
            card.set_camera_values(self._camera_values)

    def _apply_camera_count(self) -> None:
        try:
            count = max(1, min(8, int(self.count_var.get())))
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num"))
            return
        self.count_var.set(str(count))
        lr, lc = self._layout_dims()
        while lr * lc < count:
            lc += 1
            if lr * lc < count:
                lr += 1
        self.layout_rows_var.set(str(lr))
        self.layout_cols_var.set(str(lc))
        self._rebuild_cards(count)

    def _apply_layout_shape(self) -> None:
        try:
            lr = max(1, int(self.layout_rows_var.get()))
            lc = max(1, int(self.layout_cols_var.get()))
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_layout_pos_int"))
            return
        self.layout_rows_var.set(str(lr))
        self.layout_cols_var.set(str(lc))
        count = len(self._cards) or lr * lc
        if lr * lc < count:
            count = lr * lc
            self.count_var.set(str(count))
        self._rebuild_cards(count)

    def _rebuild_cards(self, count: int) -> None:
        self.stop_all_previews()
        for card in self._cards:
            card.destroy()
        self._cards.clear()
        ctx = self._card_context()
        for i in range(count):
            uid = chr(65 + i)
            card = CameraUnitCard(
                self._cards_frame,
                unit_id=uid,
                camera_values=self._camera_values,
                on_change=lambda: None,
                on_remove=lambda: None,
                **ctx,
            )
            card.set_remove_handler(lambda c=card: self._remove_camera_card(c))
            card.pack(fill=tk.X, pady=(0, 10))
            labels = card._position_labels()
            if i < len(labels):
                card.position_var.set(labels[i])
                card._on_position_change()
            else:
                card.position_var.set(labels[-1] if labels else "")
                card._on_position_change()
            self._cards.append(card)
        self.count_var.set(str(count))

    def _remove_camera_card(self, card: CameraUnitCard) -> None:
        if len(self._cards) <= 1:
            messagebox.showwarning(t("dlg_param_error"), t("dlg_min_one_camera"))
            return
        if card not in self._cards:
            return
        card.stop_preview()
        self._cards.remove(card)
        card.destroy()
        self.count_var.set(str(len(self._cards)))
        for i, remaining in enumerate(self._cards):
            remaining.unit_id = chr(65 + i)
            remaining.configure(text=t("cam_card_title", uid=remaining.unit_id))

    def load_units(
        self,
        units: List[TableUnitConfig],
        layout_enabled: bool,
        layout_rows: int,
        layout_cols: int,
    ) -> None:
        self.multi_enable_var.set(layout_enabled)
        self.layout_rows_var.set(str(layout_rows))
        self.layout_cols_var.set(str(layout_cols))
        count = len(units) if units else max(1, layout_rows * layout_cols)
        self.count_var.set(str(count))
        self._rebuild_cards(count)
        ctx = self._card_context()
        for card in self._cards:
            card.update_layout_context(**ctx)
        for i, unit in enumerate(units):
            if i < len(self._cards):
                self._cards[i].load_from_unit(unit, i)

    def collect_units(self) -> tuple[bool, int, int, List[TableUnitConfig]]:
        lr, lc = self._layout_dims()
        return self.multi_enable_var.get(), lr, lc, [card.to_unit_config() for card in self._cards]

    def stop_all_previews(self) -> None:
        for card in self._cards:
            card.stop_preview()

    def destroy(self) -> None:
        self.stop_all_previews()
        super().destroy()
