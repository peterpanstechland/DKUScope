from __future__ import annotations

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import List

from .building_types_tab import BuildingTypesTab
from .camera_calibration_tab import CameraCalibrationTab
from .camera_preview import CameraPreviewWidget
from .camera_service import enumerate_cameras, test_camera
from .config_manager import load_config, save_config
from .config_schema import (
    LayoutConfig,
    ProjectConfig,
    TableUnitConfig,
)
from .detection_monitor import DetectionMonitorWidget
from .detection_runner import DetectionRunner, DetectionStatus
from .i18n import SUPPORTED_LANGUAGES, get_lang, set_lang, t
from .ota_service import (
    ReleaseInfo,
    UpdateCheckResult,
    UpdateWorker,
    apply_update,
    can_apply_update,
    format_size,
    get_current_version,
    open_release_page,
)
from .projection_calibration_service import run_projection_calibration


class ControlStationApp(tk.Tk):
    def __init__(self, default_config_path: Path | None = None) -> None:
        super().__init__()
        self.default_config_path = default_config_path
        self.config_data: ProjectConfig = load_config(default_config_path)
        self.cameras: list = []
        self.detection_runner = DetectionRunner(on_status=self._on_detection_status)
        self._ota_worker: UpdateWorker | None = None
        self._ota_staged_root: Path | None = None
        self._ota_progress: tk.Toplevel | None = None
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
        ttk.Button(top, text=t("btn_check_update"), command=self.on_check_update).pack(side=tk.LEFT, padx=4)

        self.status_var = tk.StringVar(value=t("status_ready"))
        ttk.Label(top, textvariable=self.status_var).pack(side=tk.RIGHT, padx=(20, 0))

        self.version_var = tk.StringVar(value=t("lbl_app_version", v=get_current_version()))
        ttk.Label(top, textvariable=self.version_var).pack(side=tk.RIGHT, padx=(8, 0))

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

    # ── OTA update ──────────────────────────────────────────

    def on_check_update(self) -> None:
        if self._ota_worker and self._ota_worker._thread and self._ota_worker._thread.is_alive():
            return
        self.status_var.set(t("ota_checking"))
        self._ota_worker = UpdateWorker(on_check_done=lambda r: self.after(0, lambda: self._on_update_checked(r)))
        self._ota_worker.check_async()

    def _on_update_checked(self, result: UpdateCheckResult) -> None:
        self.status_var.set(t("status_ready"))
        if result.error:
            messagebox.showerror(t("ota_check_fail"), t("ota_check_fail_fmt", err=result.error))
            return
        if not result.latest:
            messagebox.showerror(t("ota_check_fail"), t("ota_check_fail_fmt", err="No release"))
            return
        if not result.update_available:
            messagebox.showinfo(t("btn_check_update"), t("ota_up_to_date", v=result.current_version))
            return
        latest = result.latest
        notes = latest.body or t("ota_no_notes")
        if len(notes) > 500:
            notes = notes[:500] + "…"
        if not messagebox.askyesno(
            t("ota_available_title"),
            t(
                "ota_available_fmt",
                current=result.current_version,
                latest=latest.version,
                size=format_size(latest.size),
                notes=notes,
            ),
        ):
            return
        self._start_update_download(latest)

    def _start_update_download(self, release: ReleaseInfo) -> None:
        self._show_ota_progress(t("ota_downloading"))
        self._ota_worker = UpdateWorker(
            on_check_done=lambda _r: None,
            on_download_progress=lambda done, total: self.after(
                0, lambda d=done, t=total: self._update_ota_progress(d, t),
            ),
            on_download_done=lambda staged, err: self.after(
                0, lambda s=staged, e=err: self._on_update_downloaded(release, s, e),
            ),
        )
        self._ota_worker.download_async(release)

    def _show_ota_progress(self, message: str) -> None:
        if self._ota_progress:
            self._ota_progress.destroy()
        dlg = tk.Toplevel(self)
        dlg.title(t("btn_check_update"))
        dlg.transient(self)
        dlg.grab_set()
        dlg.resizable(False, False)
        frame = ttk.Frame(dlg, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        self._ota_progress_label = ttk.Label(frame, text=message)
        self._ota_progress_label.pack(anchor="w", pady=(0, 8))
        self._ota_progress_bar = ttk.Progressbar(frame, mode="indeterminate", length=320)
        self._ota_progress_bar.pack(fill=tk.X)
        self._ota_progress_bar.start(12)
        self._ota_progress = dlg

    def _update_ota_progress(self, downloaded: int, total: int) -> None:
        if not self._ota_progress:
            return
        bar = self._ota_progress_bar
        if total > 0:
            if bar.cget("mode") != "determinate":
                bar.stop()
                bar.configure(mode="determinate", maximum=total)
            bar["value"] = min(downloaded, total)
            pct = int(downloaded * 100 / total)
            self._ota_progress_label.configure(
                text=f"{t('ota_downloading')} {pct}% ({format_size(downloaded)} / {format_size(total)})",
            )
        else:
            self._ota_progress_label.configure(text=t("ota_downloading"))

    def _close_ota_progress(self) -> None:
        if self._ota_progress:
            self._ota_progress.grab_release()
            self._ota_progress.destroy()
            self._ota_progress = None

    def _on_update_downloaded(self, release: ReleaseInfo, staged_root: Path, err: Exception | None) -> None:
        self._close_ota_progress()
        if err:
            messagebox.showerror(t("ota_download_fail"), t("ota_download_fail_fmt", err=str(err)))
            return

        self._ota_staged_root = staged_root
        if can_apply_update():
            if messagebox.askyesno(
                t("ota_ready_title"),
                t("ota_ready_fmt", v=release.version),
            ):
                self._install_downloaded_update(release)
        else:
            messagebox.showinfo(
                t("ota_ready_title"),
                t("ota_dev_ready_fmt", v=release.version, path=staged_root),
            )
            open_release_page(release.tag)

    def _install_downloaded_update(self, release: ReleaseInfo) -> None:
        if not self._ota_staged_root:
            return
        try:
            self.detection_runner.stop()
            self.camera_preview.stop()
            self.camera_cal_tab.stop_all_previews()
            apply_update(self._ota_staged_root)
        except Exception as exc:
            messagebox.showerror(t("ota_install_fail"), str(exc))
            return
        self.destroy()

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
        self.tab_cameras = ttk.Frame(notebook, padding=0)
        self.tab_classes = ttk.Frame(notebook, padding=12)
        self.tab_layout = ttk.Frame(notebook, padding=12)
        self.tab_detection = ttk.Frame(notebook, padding=12)
        notebook.add(self.tab_general, text=t("tab_general"))
        notebook.add(self.tab_cameras, text=t("tab_cameras"))
        notebook.add(self.tab_classes, text=t("tab_classes"))
        notebook.add(self.tab_layout, text=t("tab_layout"))
        notebook.add(self.tab_detection, text=t("tab_detection"))
        self._build_general_tab()
        self._build_cameras_tab()
        self._build_classes_tab()
        self._build_layout_tab()
        self._build_detection_tab()

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

        ttk.Separator(panel, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=6)

        detect_frame = ttk.LabelFrame(panel, text=t("panel_detection"), padding=4)
        detect_frame.pack(fill=tk.X, pady=(0, 6))
        detect_ctrl = ttk.Frame(detect_frame)
        detect_ctrl.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(detect_ctrl, text=t("lbl_ws_port")).pack(side=tk.LEFT)
        self.ws_port_var = tk.StringVar(value="8765")
        ttk.Entry(detect_ctrl, textvariable=self.ws_port_var, width=6).pack(side=tk.LEFT, padx=(2, 8))
        ttk.Label(detect_ctrl, text=t("lbl_detect_fps")).pack(side=tk.LEFT)
        self.detect_fps_var = tk.StringVar(value="10")
        ttk.Entry(detect_ctrl, textvariable=self.detect_fps_var, width=5).pack(side=tk.LEFT, padx=(2, 0))
        detect_btn = ttk.Frame(detect_frame)
        detect_btn.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(detect_btn, text=t("btn_start_detection"), command=self.on_start_detection).pack(side=tk.LEFT, padx=(0, 4), fill=tk.X, expand=True)
        ttk.Button(detect_btn, text=t("btn_stop_detection"), command=self.on_stop_detection).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.detection_status_var = tk.StringVar(value=t("detection_stopped"))
        ttk.Label(detect_frame, textvariable=self.detection_status_var, wraplength=400).pack(anchor="w")

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
            rows, cols = 4, 8
        self.camera_preview.configure_grid_overlay(self.preview_grid_var.get(), rows, cols)

    def _build_cameras_tab(self) -> None:
        self.camera_cal_tab = CameraCalibrationTab(
            self.tab_cameras,
            get_global_camera_settings=self._get_global_camera_settings,
            get_grid_size=self._get_grid_size,
        )
        self.camera_cal_tab.pack(fill=tk.BOTH, expand=True)

    def _get_global_camera_settings(self) -> tuple[int, int, int]:
        try:
            return (
                int(self.cam_width_var.get()),
                int(self.cam_height_var.get()),
                int(self.cam_fps_var.get()),
            )
        except ValueError:
            return 640, 480, 30

    def _get_grid_size(self) -> tuple[int, int]:
        try:
            return int(self.grid_rows_var.get()), int(self.grid_cols_var.get())
        except ValueError:
            return 4, 8

    # ── general tab ─────────────────────────────────────────

    def _build_general_tab(self) -> None:
        root = self.tab_general
        for i in range(4):
            root.columnconfigure(i, weight=1)
        ttk.Label(root, text=t("sect_table"), font=("", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.table_width_var = tk.StringVar()
        self.table_height_var = tk.StringVar()
        self.cell_width_var = tk.StringVar()
        self.cell_height_var = tk.StringVar()
        self.block_width_var = tk.StringVar()
        self.block_height_var = tk.StringVar()
        self._add_labeled_entry(root, t("lbl_table_width"), self.table_width_var, 1, 0)
        self._add_labeled_entry(root, t("lbl_table_height"), self.table_height_var, 1, 2)
        self._add_labeled_entry(root, t("lbl_cell_width"), self.cell_width_var, 2, 0)
        self._add_labeled_entry(root, t("lbl_cell_height"), self.cell_height_var, 2, 2)
        self._add_labeled_entry(root, t("lbl_block_width"), self.block_width_var, 3, 0)
        self._add_labeled_entry(root, t("lbl_block_height"), self.block_height_var, 3, 2)
        ttk.Separator(root, orient=tk.HORIZONTAL).grid(row=4, column=0, columnspan=4, sticky="ew", pady=12)
        ttk.Label(root, text=t("sect_grid"), font=("", 11, "bold")).grid(row=5, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.grid_rows_var = tk.StringVar()
        self.grid_cols_var = tk.StringVar()
        self.grid_gap_var = tk.StringVar()
        self.grid_border_var = tk.StringVar()
        self._add_labeled_entry(root, t("lbl_grid_rows"), self.grid_rows_var, 6, 0)
        self._add_labeled_entry(root, t("lbl_grid_cols"), self.grid_cols_var, 6, 2)
        self._add_labeled_entry(root, t("lbl_grid_gap"), self.grid_gap_var, 7, 0)
        self._add_labeled_entry(root, t("lbl_border"), self.grid_border_var, 7, 2)
        ttk.Separator(root, orient=tk.HORIZONTAL).grid(row=8, column=0, columnspan=4, sticky="ew", pady=12)
        ttk.Label(root, text=t("sect_block"), font=("", 11, "bold")).grid(row=9, column=0, columnspan=4, sticky="w", pady=(0, 8))
        self.block_studs_w_var = tk.StringVar()
        self.block_studs_h_var = tk.StringVar()
        self.block_size_cm_var = tk.StringVar()
        self.plate_studs_w_var = tk.StringVar()
        self.plate_studs_h_var = tk.StringVar()
        self.plate_size_cm_var = tk.StringVar()
        self._add_labeled_entry(root, t("lbl_block_w"), self.block_studs_w_var, 10, 0)
        self._add_labeled_entry(root, t("lbl_block_h"), self.block_studs_h_var, 10, 2)
        self._add_labeled_entry(root, t("lbl_block_cm"), self.block_size_cm_var, 11, 0)
        self._add_labeled_entry(root, t("lbl_plate_w"), self.plate_studs_w_var, 12, 0)
        self._add_labeled_entry(root, t("lbl_plate_h"), self.plate_studs_h_var, 12, 2)
        self._add_labeled_entry(root, t("lbl_plate_cm"), self.plate_size_cm_var, 13, 0)

    # ── building types tab ──────────────────────────────────

    def _build_classes_tab(self) -> None:
        self.building_types_tab = BuildingTypesTab(
            self.tab_classes,
            get_camera_settings=self._get_camera_settings_with_index,
        )
        self.building_types_tab.pack(fill=tk.BOTH, expand=True)

    def _get_camera_settings_with_index(self) -> tuple[int, int, int, int]:
        return (
            int(self.camera_index_var.get()),
            int(self.cam_width_var.get()),
            int(self.cam_height_var.get()),
            int(self.cam_fps_var.get()),
        )

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

    def _build_detection_tab(self) -> None:
        root = self.tab_detection
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.detection_monitor = DetectionMonitorWidget(root)
        self.detection_monitor.grid(row=0, column=0, sticky="nsew")
        self._refresh_detection_monitor_colors()

    def _refresh_detection_monitor_colors(self) -> None:
        colors = {}
        for cls in self.config_data.classes:
            if cls.color_hex:
                colors[cls.class_id] = cls.color_hex
        self.detection_monitor.set_class_colors(colors)

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
        self.table_width_var.set(str(cfg.table.table_width_mm))
        self.table_height_var.set(str(cfg.table.table_height_mm))
        self.cell_width_var.set(str(cfg.table.cell_width_mm))
        self.cell_height_var.set(str(cfg.table.cell_height_mm))
        self.block_width_var.set(str(cfg.table.block_width_mm))
        self.block_height_var.set(str(cfg.table.block_height_mm))
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
        self.proj_cam_var.set(str(cfg.projection.projector_camera_index))
        self.proj_w_var.set(str(cfg.projection.projector_width))
        self.proj_h_var.set(str(cfg.projection.projector_height))
        self._refresh_projection_status()

        self.building_types_tab.load_classes(cfg.classes)

        self.layout_enabled_var.set(cfg.layout.enabled)
        self.layout_rows_var.set(str(cfg.layout.layout_rows))
        self.layout_cols_var.set(str(cfg.layout.layout_cols))
        self._sync_unit_tree(cfg.layout.units)
        self.camera_cal_tab.load_units(
            cfg.layout.units,
            cfg.layout.enabled,
            cfg.layout.layout_rows,
            cfg.layout.layout_cols,
        )
        self._refresh_detection_monitor_colors()

    def _sync_unit_tree(self, units: List[TableUnitConfig]) -> None:
        for item in self.unit_tree.get_children():
            self.unit_tree.delete(item)
        for u in units:
            self.unit_tree.insert("", tk.END, values=(
                u.unit_id, u.camera_index, u.grid_row_offset, u.grid_col_offset,
                u.grid_rows, u.grid_cols,
            ))

    def _collect_config_from_form(self) -> ProjectConfig:
        cfg = self.config_data
        cfg.camera.index = int(self.camera_index_var.get())
        cfg.camera.width = int(self.cam_width_var.get())
        cfg.camera.height = int(self.cam_height_var.get())
        cfg.camera.fps = int(self.cam_fps_var.get())
        cfg.table.table_width_mm = float(self.table_width_var.get())
        cfg.table.table_height_mm = float(self.table_height_var.get())
        cfg.table.cell_width_mm = float(self.cell_width_var.get())
        cfg.table.cell_height_mm = float(self.cell_height_var.get())
        cfg.table.block_width_mm = float(self.block_width_var.get())
        cfg.table.block_height_mm = float(self.block_height_var.get())
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

        cfg.classes = self.building_types_tab.collect_classes()

        units: List[TableUnitConfig] = []
        layout_enabled, layout_rows, layout_cols, units = self.camera_cal_tab.collect_units()
        cfg.layout = LayoutConfig(
            enabled=layout_enabled,
            layout_rows=layout_rows,
            layout_cols=layout_cols,
            units=units,
        )
        self.layout_enabled_var.set(layout_enabled)
        self.layout_rows_var.set(str(layout_rows))
        self.layout_cols_var.set(str(layout_cols))
        self._sync_unit_tree(units)
        if len(units) == 1:
            cfg.camera.index = units[0].camera_index
            if units[0].calibration.enabled:
                cfg.calibration = units[0].calibration
        return cfg

    # ── camera actions ──────────────────────────────────────

    def refresh_cameras(self) -> None:
        self.cameras = enumerate_cameras()
        values = [str(cam.index) for cam in self.cameras] or ["0"]
        self.camera_combo["values"] = values
        if self.camera_index_var.get() not in values:
            self.camera_index_var.set(values[0])
        self.camera_cal_tab.set_camera_values(values)
        self.status_var.set(t("cameras_found", n=len(self.cameras)))

    def _refresh_projection_status(self) -> None:
        p = self.config_data.projection
        if p.enabled and p.warp_matrix:
            self.proj_status_var.set(t("calibrated_fmt", w=p.projector_width, h=p.projector_height))
        else:
            self.proj_status_var.set(t("not_calibrated"))

    # ── detection actions ─────────────────────────────────

    def _has_color_calibration(self, config: ProjectConfig) -> bool:
        return any(cls.calibrated_lab and len(cls.calibrated_lab) == 3 for cls in config.classes)

    def _on_detection_status(self, status: DetectionStatus) -> None:
        self.after(0, lambda: self._apply_detection_status(status))

    def _apply_detection_status(self, status: DetectionStatus) -> None:
        if status.error:
            self.detection_status_var.set(t("detection_error_fmt", err=status.error))
            self.detection_monitor.show_idle()
            messagebox.showerror(t("panel_detection"), status.error)
            return
        if status.running:
            self.detection_status_var.set(t(
                "detection_running_fmt",
                seq=status.seq,
                changed=status.changed_count,
                buildings=status.building_count,
                rows=status.grid_rows,
                cols=status.grid_cols,
                clients=status.client_count,
                url=status.ws_url,
            ))
            coverage = status.metrics.get("coverage_ratio", 0.0)
            self.detection_monitor.update_frame(
                seq=status.seq,
                rows=status.grid_rows,
                cols=status.grid_cols,
                cells=status.cells,
                changed_cells=status.changed_cells,
                client_count=status.client_count,
                ws_url=status.ws_url,
                building_count=status.building_count,
                coverage=coverage,
            )
        else:
            self.detection_status_var.set(t("detection_stopped"))
            self.detection_monitor.show_idle()

    def on_start_detection(self) -> None:
        if self.detection_runner.is_running:
            messagebox.showinfo(t("panel_detection"), t("dlg_detection_running"))
            return
        try:
            config = self._collect_config_from_form()
            port = int(self.ws_port_var.get())
            fps = float(self.detect_fps_var.get())
        except ValueError:
            messagebox.showerror(t("dlg_param_error"), t("dlg_check_num_fmt"))
            return
        if not self._has_color_calibration(config):
            messagebox.showwarning(t("panel_detection"), t("dlg_no_color_calib"))
            return
        self.config_data = config
        self._refresh_detection_monitor_colors()
        self.camera_preview.stop()
        self.camera_cal_tab.stop_all_previews()
        try:
            self.detection_runner.start(config, port=port, target_fps=fps)
        except Exception as exc:
            messagebox.showerror(t("panel_detection"), str(exc))

    def on_stop_detection(self) -> None:
        self.detection_runner.stop()
        self.detection_status_var.set(t("detection_stopped"))
        self.detection_monitor.show_idle()

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
            sub_r, sub_c = 4, 8
        sub_r = max(1, sub_r // lr)
        sub_c = max(1, sub_c // lc)
        units: List[TableUnitConfig] = []
        ci = 0
        for r in range(lr):
            for c in range(lc):
                units.append(TableUnitConfig(
                    unit_id=chr(65 + ci),
                    camera_index=ci,
                    grid_row_offset=r * sub_r,
                    grid_col_offset=c * sub_c,
                    grid_rows=sub_r,
                    grid_cols=sub_c,
                ))
                ci += 1
        self.layout_enabled_var.set(True)
        self.layout_rows_var.set(str(lr))
        self.layout_cols_var.set(str(lc))
        self.camera_cal_tab.load_units(units, True, lr, lc)
        self._sync_unit_tree(units)
        self.status_var.set(t("units_generated", r=lr, c=lc, t=lr * lc))

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
        self.detection_runner.stop()
        self.camera_preview.stop()
        self.camera_cal_tab.stop_all_previews()
        super().destroy()
