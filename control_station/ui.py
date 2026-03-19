from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List

from .calibration_service import run_four_point_calibration
from .camera_preview import CameraPreviewWidget
from .camera_service import enumerate_cameras, test_camera
from .color_pick_service import run_color_pick
from .config_manager import load_config, save_config
from .config_schema import (
    BuildingClassConfig,
    LayoutConfig,
    ProjectConfig,
    TableUnitConfig,
)
from .i18n import SUPPORTED_LANGUAGES, get_lang, set_lang, t
from .projection_calibration_service import run_projection_calibration


class ControlStationApp(tk.Tk):
    def __init__(self, default_config_path: Path | None = None) -> None:
        super().__init__()
        self.default_config_path = default_config_path
        self.config_data: ProjectConfig = load_config(default_config_path)
        self.cameras: list = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.title(t("app_title"))
        self.geometry("1360x800")
        self.minsize(1200, 720)
        self._build_header()
        self._build_body()
        self._load_config_to_form()
        self.refresh_cameras()

    def _rebuild_ui(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        self._build_ui()

    # ── header ──────────────────────────────────────────────

    def _build_header(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.pack(fill=tk.X)

        ttk.Button(top, text=t("btn_load"), command=self.on_load_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text=t("btn_save"), command=self.on_save_file).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text=t("btn_save_default"), command=self.on_save_default).pack(side=tk.LEFT, padx=4)
        ttk.Button(top, text=t("btn_reset_form"), command=self._load_config_to_form).pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value=t("status_ready"))
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT, padx=(20, 0))

        self.lang_var = tk.StringVar(value=get_lang())
        lang_combo = ttk.Combobox(
            top, textvariable=self.lang_var,
            values=list(SUPPORTED_LANGUAGES.keys()), state="readonly", width=8,
        )
        lang_combo.pack(side=tk.RIGHT, padx=4)
        lang_combo.bind("<<ComboboxSelected>>", self._on_lang_changed)
        ttk.Label(top, text="Lang").pack(side=tk.RIGHT)

    def _on_lang_changed(self, _event: object) -> None:
        new_lang = self.lang_var.get()
        if new_lang != get_lang():
            set_lang(new_lang)
            self._rebuild_ui()

    # ── body ────────────────────────────────────────────────

    def _build_body(self) -> None:
        body = ttk.Frame(self)
        body.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=0)
        body.rowconfigure(0, weight=1)
        self._build_left_tabs(body)
        self._build_right_camera_panel(body)

    def _build_left_tabs(self, body: ttk.Frame) -> None:
        notebook = ttk.Notebook(body)
        notebook.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.tab_general = ttk.Frame(notebook, padding=12)
        self.tab_classes = ttk.Frame(notebook, padding=12)
        self.tab_layout = ttk.Frame(notebook, padding=12)
        notebook.add(self.tab_general, text=t("tab_general"))
        notebook.add(self.tab_classes, text=t("tab_classes"))
        notebook.add(self.tab_layout, text=t("tab_layout"))
        self._build_general_tab()
        self._build_classes_tab()
        self._build_layout_tab()

    # ── right camera panel ──────────────────────────────────

    def _build_right_camera_panel(self, body: ttk.Frame) -> None:
        panel = ttk.LabelFrame(body, text=t("panel_camera"), padding=8)
        panel.grid(row=0, column=1, sticky="nsew")

        cam_ctrl = ttk.Frame(panel)
        cam_ctrl.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(cam_ctrl, text=t("lbl_camera")).pack(side=tk.LEFT)
        self.camera_index_var = tk.StringVar(value="0")
        self.camera_combo = ttk.Combobox(cam_ctrl, textvariable=self.camera_index_var, state="readonly", width=6)
        self.camera_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(cam_ctrl, text=t("btn_refresh"), command=self.refresh_cameras, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Button(cam_ctrl, text=t("btn_test"), command=self.on_test_camera, width=5).pack(side=tk.LEFT, padx=2)

        res_frame = ttk.Frame(panel)
        res_frame.pack(fill=tk.X, pady=(0, 4))
        self.cam_width_var = tk.StringVar()
        self.cam_height_var = tk.StringVar()
        self.cam_fps_var = tk.StringVar()
        ttk.Label(res_frame, text=t("lbl_width")).pack(side=tk.LEFT)
        ttk.Entry(res_frame, textvariable=self.cam_width_var, width=6).pack(side=tk.LEFT, padx=(2, 6))
        ttk.Label(res_frame, text=t("lbl_height")).pack(side=tk.LEFT)
        ttk.Entry(res_frame, textvariable=self.cam_height_var, width=6).pack(side=tk.LEFT, padx=(2, 6))
        ttk.Label(res_frame, text="FPS").pack(side=tk.LEFT)
        ttk.Entry(res_frame, textvariable=self.cam_fps_var, width=5).pack(side=tk.LEFT, padx=(2, 0))

        self.camera_preview = CameraPreviewWidget(panel, preview_width=420, preview_height=315)
        self.camera_preview.pack(pady=(4, 4))
        self.camera_preview.set_start_callback(self._sync_preview_params)

        opts = ttk.Frame(panel)
        opts.pack(fill=tk.X, pady=(0, 4))
        self.preview_grid_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text=t("chk_grid_overlay"), variable=self.preview_grid_var, command=self._on_preview_grid_toggle).pack(side=tk.LEFT)
        self.calib_status_var = tk.StringVar(value=t("not_calibrated"))
        ttk.Label(opts, textvariable=self.calib_status_var).pack(side=tk.RIGHT)

        calib_row = ttk.Frame(panel)
        calib_row.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(calib_row, text=t("lbl_calib_target")).pack(side=tk.LEFT)
        self.calib_target_var = tk.StringVar(value=t("calib_target_global"))
        self.calib_target_combo = ttk.Combobox(calib_row, textvariable=self.calib_target_var, state="readonly", width=14)
        self.calib_target_combo["values"] = [t("calib_target_global")]
        self.calib_target_combo.pack(side=tk.LEFT, padx=4)
        ttk.Button(calib_row, text=t("btn_bottom_calib"), command=self.on_open_calibration_wizard).pack(side=tk.LEFT, padx=2, fill=tk.X, expand=True)

        ttk.Separator(panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        proj_frame = ttk.LabelFrame(panel, text=t("panel_proj_calib"), padding=4)
        proj_frame.pack(fill=tk.X)
        proj_ctrl = ttk.Frame(proj_frame)
        proj_ctrl.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(proj_ctrl, text=t("lbl_proj_cam")).pack(side=tk.LEFT)
        self.proj_cam_var = tk.StringVar(value="1")
        ttk.Entry(proj_ctrl, textvariable=self.proj_cam_var, width=4).pack(side=tk.LEFT, padx=4)
        ttk.Label(proj_ctrl, text=t("lbl_resolution")).pack(side=tk.LEFT)
        self.proj_w_var = tk.StringVar(value="1920")
        self.proj_h_var = tk.StringVar(value="1080")
        ttk.Entry(proj_ctrl, textvariable=self.proj_w_var, width=5).pack(side=tk.LEFT, padx=2)
        ttk.Label(proj_ctrl, text="x").pack(side=tk.LEFT)
        ttk.Entry(proj_ctrl, textvariable=self.proj_h_var, width=5).pack(side=tk.LEFT, padx=2)
        self.proj_status_var = tk.StringVar(value=t("not_calibrated"))
        ttk.Label(proj_frame, textvariable=self.proj_status_var).pack(anchor="w")
        ttk.Button(proj_frame, text=t("btn_proj_calib"), command=self.on_projection_calibration).pack(fill=tk.X, pady=(4, 0))

    def _sync_preview_params(self) -> None:
        try:
            self.camera_preview.configure_camera(int(self.camera_index_var.get()), int(self.cam_width_var.get()), int(self.cam_height_var.get()), int(self.cam_fps_var.get()))
            self.camera_preview.configure_grid_overlay(self.preview_grid_var.get(), int(self.grid_rows_var.get()), int(self.grid_cols_var.get()))
        except ValueError:
            pass

    def _on_preview_grid_toggle(self) -> None:
        try:
            rows, cols = int(self.grid_rows_var.get()), int(self.grid_cols_var.get())
        except ValueError:
            rows, cols = 16, 16
        self.camera_preview.configure_grid_overlay(self.preview_grid_var.get(), rows, cols)

    # ── general tab ─────────────────────────────────────────

    def _build_general_tab(self) -> None:
        root = self.tab_general
        for i in range(4):
            root.columnconfigure(i, weight=1)
        ttk.Label(root, text=t("sect_grid"), font=("", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.grid_rows_var = tk.StringVar()
        self.grid_cols_var = tk.StringVar()
        self.grid_gap_var = tk.StringVar()
        self.grid_border_var = tk.StringVar()
        self._add_labeled_entry(root, t("lbl_grid_rows"), self.grid_rows_var, 1, 0)
        self._add_labeled_entry(root, t("lbl_grid_cols"), self.grid_cols_var, 1, 2)
        self._add_labeled_entry(root, t("lbl_grid_gap"), self.grid_gap_var, 2, 0)
        self._add_labeled_entry(root, t("lbl_border"), self.grid_border_var, 2, 2)
        ttk.Separator(root, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=4, sticky="ew", pady=12)
        ttk.Label(root, text=t("sect_block"), font=("", 11, "bold")).grid(row=4, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.block_studs_w_var = tk.StringVar()
        self.block_studs_h_var = tk.StringVar()
        self.block_size_cm_var = tk.StringVar()
        self.plate_studs_w_var = tk.StringVar()
        self.plate_studs_h_var = tk.StringVar()
        self.plate_size_cm_var = tk.StringVar()
        self._add_labeled_entry(root, t("lbl_block_w"), self.block_studs_w_var, 5, 0)
        self._add_labeled_entry(root, t("lbl_block_h"), self.block_studs_h_var, 5, 2)
        self._add_labeled_entry(root, t("lbl_block_cm"), self.block_size_cm_var, 6, 0)
        self._add_labeled_entry(root, t("lbl_plate_w"), self.plate_studs_w_var, 7, 0)
        self._add_labeled_entry(root, t("lbl_plate_h"), self.plate_studs_h_var, 7, 2)
        self._add_labeled_entry(root, t("lbl_plate_cm"), self.plate_size_cm_var, 8, 0)

    # ── classes tab ─────────────────────────────────────────

    def _build_classes_tab(self) -> None:
        root = self.tab_classes
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        columns = ("class_id", "label_zh", "label_en", "color_zh", "color_en", "color_hex", "calibrated_lab", "examples_zh", "examples_en", "is_fixed", "footprints")
        self.class_tree = ttk.Treeview(root, columns=columns, show="headings", height=12)
        col_heads = {
            "class_id": t("col_class_id"), "label_zh": t("lbl_label_zh"), "label_en": t("lbl_label_en"),
            "color_zh": t("lbl_color_name_zh"), "color_en": t("lbl_color_name_en"), "color_hex": t("col_color_hex"),
            "calibrated_lab": t("col_calib_lab"), "examples_zh": t("lbl_examples_zh"), "examples_en": t("lbl_examples_en"),
            "is_fixed": t("col_fixed"), "footprints": t("col_footprints"),
        }
        col_widths = {
            "class_id": 55, "label_zh": 80, "label_en": 90, "color_zh": 65, "color_en": 65, "color_hex": 75,
            "calibrated_lab": 105, "examples_zh": 130, "examples_en": 130, "is_fixed": 50, "footprints": 120,
        }
        for col in columns:
            self.class_tree.heading(col, text=col_heads[col])
            self.class_tree.column(col, width=col_widths[col], anchor="center")
        self.class_tree.grid(row=0, column=0, sticky="nsew")
        self.class_tree.bind("<<TreeviewSelect>>", self.on_class_selected)
        sb = ttk.Scrollbar(root, orient=tk.VERTICAL, command=self.class_tree.yview)
        self.class_tree.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")

        form = ttk.LabelFrame(root, text=t("lbl_edit"), padding=8)
        form.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for i in range(8):
            form.columnconfigure(i, weight=1)
        self.class_id_var = tk.StringVar()
        self.class_label_zh_var = tk.StringVar()
        self.class_label_en_var = tk.StringVar()
        self.class_color_zh_var = tk.StringVar()
        self.class_color_en_var = tk.StringVar()
        self.class_color_hex_var = tk.StringVar()
        self.class_calibrated_lab_var = tk.StringVar()
        self.class_examples_zh_var = tk.StringVar()
        self.class_examples_en_var = tk.StringVar()
        self.class_fixed_var = tk.BooleanVar(value=False)
        self.class_footprints_var = tk.StringVar()

        self._add_labeled_entry(form, t("lbl_class_id"), self.class_id_var, 0, 0, 1)
        self._add_labeled_entry(form, t("lbl_label_zh"), self.class_label_zh_var, 0, 2, 1)
        self._add_labeled_entry(form, t("lbl_label_en"), self.class_label_en_var, 0, 4, 1)
        self._add_labeled_entry(form, t("lbl_color_hex"), self.class_color_hex_var, 0, 6, 1)
        self._add_labeled_entry(form, t("lbl_color_name_zh"), self.class_color_zh_var, 1, 0, 1)
        self._add_labeled_entry(form, t("lbl_color_name_en"), self.class_color_en_var, 1, 2, 1)
        self._add_labeled_entry(form, t("lbl_examples_zh"), self.class_examples_zh_var, 1, 4, 1)
        self._add_labeled_entry(form, t("lbl_examples_en"), self.class_examples_en_var, 1, 6, 1)
        self._add_labeled_entry(form, t("lbl_calib_lab"), self.class_calibrated_lab_var, 2, 0, 1)
        self._add_labeled_entry(form, t("lbl_footprints"), self.class_footprints_var, 2, 2, 1)
        ttk.Button(form, text=t("btn_color_pick"), command=self.on_color_pick_from_camera).grid(row=2, column=4, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Checkbutton(form, text=t("chk_fixed"), variable=self.class_fixed_var).grid(row=2, column=6, sticky="w", pady=(6, 0))
        btns = ttk.Frame(form)
        btns.grid(row=3, column=0, columnspan=8, sticky="e", pady=(6, 0))
        ttk.Button(btns, text=t("btn_add"), command=self.on_class_add).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text=t("btn_update"), command=self.on_class_update).pack(side=tk.LEFT, padx=4)
        ttk.Button(btns, text=t("btn_delete"), command=self.on_class_delete).pack(side=tk.LEFT, padx=4)

    # ── layout tab ──────────────────────────────────────────

    def _build_layout_tab(self) -> None:
        root = self.tab_layout
        for i in range(6):
            root.columnconfigure(i, weight=1)
        ttk.Label(root, text=t("sect_layout"), font=("", 11, "bold")).grid(row=0, column=0, columnspan=6, sticky="w", pady=(0, 8))
        self.layout_enabled_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(root, text=t("chk_layout_enable"), variable=self.layout_enabled_var).grid(row=1, column=0, columnspan=2, sticky="w")
        self.layout_rows_var = tk.StringVar(value="1")
        self.layout_cols_var = tk.StringVar(value="1")
        self._add_labeled_entry(root, t("lbl_layout_rows"), self.layout_rows_var, 2, 0)
        self._add_labeled_entry(root, t("lbl_layout_cols"), self.layout_cols_var, 2, 2)
        ttk.Button(root, text=t("btn_gen_units"), command=self.on_generate_layout_units).grid(row=2, column=4, columnspan=2, sticky="ew")
        ttk.Separator(root, orient=tk.HORIZONTAL).grid(row=3, column=0, columnspan=6, sticky="ew", pady=10)

        unit_cols = ("unit_id", "camera_index", "grid_row_offset", "grid_col_offset", "grid_rows", "grid_cols")
        self.unit_tree = ttk.Treeview(root, columns=unit_cols, show="headings", height=8)
        u_keys = {"unit_id": "col_unit_id", "camera_index": "col_cam_idx", "grid_row_offset": "col_row_off", "grid_col_offset": "col_col_off", "grid_rows": "col_sub_rows", "grid_cols": "col_sub_cols"}
        for col in unit_cols:
            self.unit_tree.heading(col, text=t(u_keys[col]))
            self.unit_tree.column(col, width=120, anchor="center")
        self.unit_tree.grid(row=4, column=0, columnspan=6, sticky="nsew")
        self.unit_tree.bind("<<TreeviewSelect>>", self.on_unit_selected)
        root.rowconfigure(4, weight=1)

        uform = ttk.LabelFrame(root, text=t("lbl_edit_unit"), padding=8)
        uform.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(8, 0))
        for i in range(8):
            uform.columnconfigure(i, weight=1)
        self.unit_id_var = tk.StringVar()
        self.unit_cam_var = tk.StringVar()
        self.unit_row_off_var = tk.StringVar()
        self.unit_col_off_var = tk.StringVar()
        self.unit_rows_var = tk.StringVar()
        self.unit_cols_var = tk.StringVar()
        self._add_labeled_entry(uform, t("col_unit_id"), self.unit_id_var, 0, 0, 1)
        self._add_labeled_entry(uform, t("col_cam_idx"), self.unit_cam_var, 0, 2, 1)
        self._add_labeled_entry(uform, t("col_row_off"), self.unit_row_off_var, 0, 4, 1)
        self._add_labeled_entry(uform, t("col_col_off"), self.unit_col_off_var, 0, 6, 1)
        self._add_labeled_entry(uform, t("col_sub_rows"), self.unit_rows_var, 1, 0, 1)
        self._add_labeled_entry(uform, t("col_sub_cols"), self.unit_cols_var, 1, 2, 1)
        ubtn = ttk.Frame(uform)
        ubtn.grid(row=1, column=6, columnspan=2, sticky="e")
        ttk.Button(ubtn, text=t("btn_update_unit"), command=self.on_unit_update).pack(side=tk.LEFT, padx=4)
        ttk.Button(ubtn, text=t("btn_delete_unit"), command=self.on_unit_delete).pack(side=tk.LEFT, padx=4)

    # ── helpers ─────────────────────────────────────────────

    def _add_labeled_entry(self, parent, label, variable, row, col, parent_col_span=1):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=col + 1, columnspan=parent_col_span, sticky="ew", padx=(0, 10), pady=3)

    # ── load / collect ──────────────────────────────────────

    def _load_config_to_form(self) -> None:
        cfg = self.config_data
        self.camera_index_var.set(str(cfg.camera.index))
        self.cam_width_var.set(str(cfg.camera.width))
        self.cam_height_var.set(str(cfg.camera.height))
        self.cam_fps_var.set(str(cfg.camera.fps))
        self.grid_rows_var.set(str(cfg.grid.rows))
        self.grid_cols_var.set(str(cfg.grid.cols))
        self.grid_gap_var.set(str(cfg.grid.cell_gap_mm))
        self.grid_border_var.set(str(cfg.grid.border_mm))
        self.block_studs_w_var.set(str(cfg.block.block_studs_w))
        self.block_studs_h_var.set(str(cfg.block.block_studs_h))
        self.block_size_cm_var.set(str(cfg.block.block_size_cm))
        self.plate_studs_w_var.set(str(cfg.block.plate_studs_w))
        self.plate_studs_h_var.set(str(cfg.block.plate_studs_h))
        self.plate_size_cm_var.set(str(cfg.block.plate_size_cm))
        self._refresh_calibration_status()
        self.proj_cam_var.set(str(cfg.projection.projector_camera_index))
        self.proj_w_var.set(str(cfg.projection.projector_width))
        self.proj_h_var.set(str(cfg.projection.projector_height))
        self._refresh_projection_status()

        for item in self.class_tree.get_children():
            self.class_tree.delete(item)
        for ci in cfg.classes:
            lab_str = ",".join(f"{v:.1f}" for v in ci.calibrated_lab) if ci.calibrated_lab else ""
            self.class_tree.insert("", tk.END, values=(
                ci.class_id, ci.label, ci.label_en,
                ci.color_name, ci.color_name_en, ci.color_hex, lab_str,
                ci.building_examples, ci.building_examples_en,
                t("yes") if ci.is_fixed_default else t("no"),
                ",".join(ci.allowed_footprints),
            ))

        self.layout_enabled_var.set(cfg.layout.enabled)
        self.layout_rows_var.set(str(cfg.layout.layout_rows))
        self.layout_cols_var.set(str(cfg.layout.layout_cols))
        for item in self.unit_tree.get_children():
            self.unit_tree.delete(item)
        for u in cfg.layout.units:
            self.unit_tree.insert("", tk.END, values=(u.unit_id, u.camera_index, u.grid_row_offset, u.grid_col_offset, u.grid_rows, u.grid_cols))

    def _collect_config_from_form(self) -> ProjectConfig:
        cfg = self.config_data
        cfg.camera.index = int(self.camera_index_var.get())
        cfg.camera.width = int(self.cam_width_var.get())
        cfg.camera.height = int(self.cam_height_var.get())
        cfg.camera.fps = int(self.cam_fps_var.get())
        cfg.grid.rows = int(self.grid_rows_var.get())
        cfg.grid.cols = int(self.grid_cols_var.get())
        cfg.grid.cell_gap_mm = float(self.grid_gap_var.get())
        cfg.grid.border_mm = float(self.grid_border_var.get())
        cfg.block.block_studs_w = int(self.block_studs_w_var.get())
        cfg.block.block_studs_h = int(self.block_studs_h_var.get())
        cfg.block.block_size_cm = float(self.block_size_cm_var.get())
        cfg.block.plate_studs_w = int(self.plate_studs_w_var.get())
        cfg.block.plate_studs_h = int(self.plate_studs_h_var.get())
        cfg.block.plate_size_cm = float(self.plate_size_cm_var.get())

        classes: List[BuildingClassConfig] = []
        for iid in self.class_tree.get_children():
            row = self.class_tree.item(iid, "values")
            lab_raw = str(row[6]).strip()
            calibrated_lab = [float(v) for v in lab_raw.split(",") if v.strip()] if lab_raw else []
            classes.append(BuildingClassConfig(
                class_id=int(row[0]), label=str(row[1]), label_en=str(row[2]),
                color_name=str(row[3]), color_name_en=str(row[4]), color_hex=str(row[5]),
                building_examples=str(row[7]), building_examples_en=str(row[8]),
                is_fixed_default=str(row[9]) == t("yes"),
                allowed_footprints=[s.strip() for s in str(row[10]).split(",") if s.strip()],
                calibrated_lab=calibrated_lab,
            ))
        cfg.classes = classes

        units: List[TableUnitConfig] = []
        for iid in self.unit_tree.get_children():
            row = self.unit_tree.item(iid, "values")
            units.append(TableUnitConfig(unit_id=str(row[0]), camera_index=int(row[1]), grid_row_offset=int(row[2]), grid_col_offset=int(row[3]), grid_rows=int(row[4]), grid_cols=int(row[5])))
        cfg.layout = LayoutConfig(enabled=self.layout_enabled_var.get(), layout_rows=int(self.layout_rows_var.get()), layout_cols=int(self.layout_cols_var.get()), units=units)
        return cfg

    # ── camera actions ──────────────────────────────────────

    def refresh_cameras(self) -> None:
        self.cameras = enumerate_cameras()
        values = [str(cam.index) for cam in self.cameras] or ["0"]
        self.camera_combo["values"] = values
        if self.camera_index_var.get() not in values:
            self.camera_index_var.set(values[0])
        self.status_var.set(t("cameras_found", n=len(self.cameras)))

    def _refresh_calibration_status(self) -> None:
        c = self.config_data.calibration
        if c.enabled and len(c.source_points) == 4:
            self.calib_status_var.set(t("calibrated_fmt", w=c.output_width, h=c.output_height))
        else:
            self.calib_status_var.set(t("not_calibrated"))

    def _refresh_projection_status(self) -> None:
        p = self.config_data.projection
        if p.enabled and p.warp_matrix:
            self.proj_status_var.set(t("calibrated_fmt", w=p.projector_width, h=p.projector_height))
        else:
            self.proj_status_var.set(t("not_calibrated"))

    def _refresh_calib_targets(self) -> None:
        targets = [t("calib_target_global")]
        for iid in self.unit_tree.get_children():
            row = self.unit_tree.item(iid, "values")
            targets.append(f"Unit {row[0]} (cam {row[1]})")
        self.calib_target_combo["values"] = targets
        self.calib_target_var.set(targets[0])

    def _get_selected_unit_id(self) -> str | None:
        val = self.calib_target_var.get()
        if val == t("calib_target_global"):
            return None
        return val.split(" ")[1]

    def on_test_camera(self) -> None:
        try:
            ok = test_camera(int(self.camera_index_var.get()), int(self.cam_width_var.get()), int(self.cam_height_var.get()), int(self.cam_fps_var.get()))
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num"))
            return
        if ok:
            messagebox.showinfo(t("dlg_cam_test"), t("dlg_cam_ok"))
        else:
            messagebox.showwarning(t("dlg_cam_test"), t("dlg_cam_fail"))

    def on_open_calibration_wizard(self) -> None:
        try:
            idx, w, h, fps = int(self.camera_index_var.get()), int(self.cam_width_var.get()), int(self.cam_height_var.get()), int(self.cam_fps_var.get())
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num"))
            return
        messagebox.showinfo(t("dlg_calib_hint_title"), t("dlg_calib_hint"))
        result = run_four_point_calibration(idx, w, h, fps)
        if result is None:
            messagebox.showwarning(t("dlg_calib_result"), t("dlg_calib_fail"))
            return

        from .config_schema import CalibrationConfig
        cal = CalibrationConfig(
            enabled=True,
            source_points=result.source_points,
            destination_points=result.destination_points,
            output_width=result.output_width,
            output_height=result.output_height,
        )

        unit_id = self._get_selected_unit_id()
        if unit_id is None:
            self.config_data.calibration = cal
            self._refresh_calibration_status()
            messagebox.showinfo(t("dlg_calib_result"), t("dlg_calib_ok"))
        else:
            for u in self.config_data.layout.units:
                if u.unit_id == unit_id:
                    u.calibration = cal
                    u.camera_index = idx
                    break
            self._refresh_calibration_status()
            messagebox.showinfo(t("dlg_calib_result"), t("calib_saved_unit", uid=unit_id))

    def on_projection_calibration(self) -> None:
        try:
            cam_idx, pw, ph = int(self.proj_cam_var.get()), int(self.proj_w_var.get()), int(self.proj_h_var.get())
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_proj_param"))
            return
        messagebox.showinfo(t("dlg_proj_hint_title"), t("dlg_proj_hint"))
        result = run_projection_calibration(projector_width=pw, projector_height=ph, camera_index=cam_idx, pattern_cols=self.config_data.projection.pattern_cols, pattern_rows=self.config_data.projection.pattern_rows)
        if result is None:
            messagebox.showwarning(t("dlg_proj_title"), t("dlg_proj_fail"))
            return
        self.config_data.projection.enabled = True
        self.config_data.projection.projector_camera_index = cam_idx
        self.config_data.projection.projector_width = pw
        self.config_data.projection.projector_height = ph
        self.config_data.projection.source_points = result.source_points
        self.config_data.projection.destination_points = result.destination_points
        self.config_data.projection.warp_matrix = result.warp_matrix
        self._refresh_projection_status()
        messagebox.showinfo(t("dlg_proj_title"), t("dlg_proj_ok"))

    # ── class actions ───────────────────────────────────────

    def on_class_selected(self, _event):
        sel = self.class_tree.selection()
        if not sel:
            return
        row = self.class_tree.item(sel[0], "values")
        self.class_id_var.set(str(row[0]))
        self.class_label_zh_var.set(str(row[1]))
        self.class_label_en_var.set(str(row[2]))
        self.class_color_zh_var.set(str(row[3]))
        self.class_color_en_var.set(str(row[4]))
        self.class_color_hex_var.set(str(row[5]))
        self.class_calibrated_lab_var.set(str(row[6]))
        self.class_examples_zh_var.set(str(row[7]))
        self.class_examples_en_var.set(str(row[8]))
        self.class_fixed_var.set(str(row[9]) == t("yes"))
        self.class_footprints_var.set(str(row[10]))

    def _validate_class_form(self) -> bool:
        if not self.class_id_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_class_id_empty"))
            return False
        if not self.class_label_zh_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_label_empty"))
            return False
        if not self.class_label_en_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_label_en_empty"))
            return False
        if not self.class_color_zh_var.get().strip() or not self.class_color_en_var.get().strip():
            messagebox.showerror(t("dlg_input_error"), t("dlg_color_en_empty"))
            return False
        if not self.class_color_hex_var.get().startswith("#"):
            messagebox.showerror(t("dlg_input_error"), t("dlg_hex_prefix"))
            return False
        return True

    def _class_row_values(self):
        return (
            self.class_id_var.get().strip(),
            self.class_label_zh_var.get().strip(),
            self.class_label_en_var.get().strip(),
            self.class_color_zh_var.get().strip(),
            self.class_color_en_var.get().strip(),
            self.class_color_hex_var.get().strip(),
            self.class_calibrated_lab_var.get().strip(),
            self.class_examples_zh_var.get().strip(),
            self.class_examples_en_var.get().strip(),
            t("yes") if self.class_fixed_var.get() else t("no"),
            self.class_footprints_var.get().strip() or "1x1",
        )

    def on_class_add(self):
        if self._validate_class_form():
            self.class_tree.insert("", tk.END, values=self._class_row_values())

    def on_class_update(self):
        sel = self.class_tree.selection()
        if not sel:
            messagebox.showwarning(t("dlg_no_select"), t("dlg_select_row"))
            return
        if self._validate_class_form():
            self.class_tree.item(sel[0], values=self._class_row_values())

    def on_class_delete(self):
        sel = self.class_tree.selection()
        if not sel:
            messagebox.showwarning(t("dlg_no_select"), t("dlg_select_del"))
            return
        self.class_tree.delete(sel[0])

    def on_color_pick_from_camera(self):
        try:
            idx, w, h, fps = int(self.camera_index_var.get()), int(self.cam_width_var.get()), int(self.cam_height_var.get()), int(self.cam_fps_var.get())
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num"))
            return
        label = self.class_label_zh_var.get().strip() or self.class_label_en_var.get().strip() or "?"
        messagebox.showinfo(t("dlg_color_hint_title"), t("dlg_color_hint", label=label))
        result = run_color_pick(idx, w, h, fps, class_label=label)
        if result is None:
            messagebox.showwarning(t("dlg_color_result"), t("dlg_color_fail"))
            return
        lab_str = ",".join(f"{v:.1f}" for v in result.lab_values)
        self.class_calibrated_lab_var.set(lab_str)
        self.class_color_hex_var.set(result.hex_color)
        messagebox.showinfo(t("dlg_color_result"), t("dlg_color_ok", lab=lab_str, hex=result.hex_color))

    # ── layout actions ──────────────────────────────────────

    def on_generate_layout_units(self):
        try:
            lr, lc = int(self.layout_rows_var.get()), int(self.layout_cols_var.get())
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_layout_pos_int"))
            return
        if lr < 1 or lc < 1:
            messagebox.showerror(t("dlg_param_error"), t("dlg_layout_gte1"))
            return
        try:
            sub_r, sub_c = int(self.grid_rows_var.get()), int(self.grid_cols_var.get())
        except ValueError:
            sub_r, sub_c = 16, 16
        for item in self.unit_tree.get_children():
            self.unit_tree.delete(item)
        ci = 0
        for r in range(lr):
            for c in range(lc):
                self.unit_tree.insert("", tk.END, values=(chr(65 + ci), ci, r * sub_r, c * sub_c, sub_r, sub_c))
                ci += 1
        self.status_var.set(t("units_generated", r=lr, c=lc, t=lr * lc))
        self._refresh_calib_targets()

    def on_unit_selected(self, _event):
        sel = self.unit_tree.selection()
        if not sel:
            return
        row = self.unit_tree.item(sel[0], "values")
        self.unit_id_var.set(str(row[0]))
        self.unit_cam_var.set(str(row[1]))
        self.unit_row_off_var.set(str(row[2]))
        self.unit_col_off_var.set(str(row[3]))
        self.unit_rows_var.set(str(row[4]))
        self.unit_cols_var.set(str(row[5]))

    def on_unit_update(self):
        sel = self.unit_tree.selection()
        if not sel:
            messagebox.showwarning(t("dlg_no_select"), t("dlg_select_unit"))
            return
        self.unit_tree.item(sel[0], values=(self.unit_id_var.get().strip(), self.unit_cam_var.get().strip(), self.unit_row_off_var.get().strip(), self.unit_col_off_var.get().strip(), self.unit_rows_var.get().strip(), self.unit_cols_var.get().strip()))

    def on_unit_delete(self):
        sel = self.unit_tree.selection()
        if not sel:
            messagebox.showwarning(t("dlg_no_select"), t("dlg_select_unit_del"))
            return
        self.unit_tree.delete(sel[0])

    # ── file I/O ────────────────────────────────────────────

    def on_load_file(self):
        p = filedialog.askopenfilename(title=t("dlg_file_select"), filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not p:
            return
        self.config_data = load_config(Path(p))
        self._load_config_to_form()
        self.status_var.set(t("config_loaded", p=p))

    def on_save_file(self):
        p = filedialog.asksaveasfilename(title=t("dlg_file_save"), defaultextension=".json", filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if not p:
            return
        try:
            save_config(self._collect_config_from_form(), Path(p))
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num_fmt"))
            return
        self.status_var.set(t("config_saved", p=p))

    def on_save_default(self):
        try:
            path = save_config(self._collect_config_from_form(), self.default_config_path)
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num_fmt"))
            return
        self.status_var.set(t("config_saved_default", p=path))

    def destroy(self):
        self.camera_preview.stop()
        super().destroy()
