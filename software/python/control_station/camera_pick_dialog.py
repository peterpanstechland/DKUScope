from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, List, Optional, Tuple

from .camera_service import CameraInfo, enumerate_cameras
from .config_schema import TableUnitConfig
from .i18n import t


class CameraPickDialog(tk.Toplevel):
    """Modal dialog to pick a camera before color sampling."""

    def __init__(
        self,
        parent: tk.Widget,
        width: int,
        height: int,
        fps: int,
        default_index: int = 0,
        layout_units: Optional[List[TableUnitConfig]] = None,
        enumerate_fn: Optional[Callable[[], List[CameraInfo]]] = None,
    ) -> None:
        super().__init__(parent)
        self.title(t("dlg_pick_camera_title"))
        self.resizable(False, False)
        self.transient(parent.winfo_toplevel())
        self.grab_set()

        self._width = width
        self._height = height
        self._fps = fps
        self._layout_units = layout_units or []
        self._enumerate_fn = enumerate_fn or enumerate_cameras
        self.result: Optional[Tuple[int, int, int, int]] = None

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        ttk.Label(
            self,
            text=t("dlg_pick_camera_hint"),
            wraplength=420,
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        list_frame = ttk.Frame(self, padding=(12, 0))
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        cols = ("source", "unit", "index", "resolution")
        self.tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=8)
        self.tree.heading("source", text=t("col_cam_source"))
        self.tree.heading("unit", text=t("col_unit_id"))
        self.tree.heading("index", text=t("col_cam_idx"))
        self.tree.heading("resolution", text=t("col_cam_resolution"))
        self.tree.column("source", width=90, anchor="center")
        self.tree.column("unit", width=60, anchor="center")
        self.tree.column("index", width=70, anchor="center")
        self.tree.column("resolution", width=100, anchor="center")
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", lambda _e: self._on_ok())
        scroll = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.grid(row=0, column=1, sticky="ns")

        btn_row = ttk.Frame(self, padding=12)
        btn_row.grid(row=2, column=0, sticky="ew")
        ttk.Button(btn_row, text=t("btn_refresh_cameras"), command=self._refresh).pack(side=tk.LEFT)
        ttk.Button(btn_row, text=t("btn_cancel"), command=self._on_cancel).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn_row, text=t("btn_start_color_pick"), command=self._on_ok).pack(side=tk.RIGHT)

        self._refresh(default_index=default_index)

        self.update_idletasks()
        px = parent.winfo_rootx() + 40
        py = parent.winfo_rooty() + 40
        self.geometry(f"+{px}+{py}")

    def _refresh(self, default_index: Optional[int] = None) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)

        seen: set[int] = set()
        select_iid: Optional[str] = None
        default_idx = default_index if default_index is not None else 0

        for unit in self._layout_units:
            idx = unit.camera_index
            seen.add(idx)
            iid = f"layout-{unit.unit_id}"
            self.tree.insert(
                "", tk.END, iid=iid,
                values=(
                    t("cam_source_layout"),
                    unit.unit_id,
                    idx,
                    f"{self._width}×{self._height}",
                ),
            )
            if idx == default_idx and select_iid is None:
                select_iid = iid

        for cam in self._enumerate_fn():
            if cam.index in seen:
                continue
            iid = f"detected-{cam.index}"
            self.tree.insert(
                "", tk.END, iid=iid,
                values=(
                    t("cam_source_detected"),
                    "-",
                    cam.index,
                    f"{self._width}×{self._height}",
                ),
            )
            if cam.index == default_idx and select_iid is None:
                select_iid = iid

        if not self.tree.get_children():
            self.tree.insert("", tk.END, iid="none", values=(t("cam_none"), "-", "-", "-"))
            return

        if select_iid is None:
            select_iid = self.tree.get_children()[0]
        self.tree.selection_set(select_iid)
        self.tree.focus(select_iid)

    def _selected_index(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        if len(vals) < 3 or vals[2] == "-":
            return None
        try:
            return int(vals[2])
        except ValueError:
            return None

    def _on_ok(self) -> None:
        idx = self._selected_index()
        if idx is None:
            messagebox.showwarning(t("dlg_pick_camera_title"), t("dlg_pick_camera_none"), parent=self)
            return
        self.result = (idx, self._width, self._height, self._fps)
        self.grab_release()
        self.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self.grab_release()
        self.destroy()


def ask_camera_for_color_pick(
    parent: tk.Widget,
    width: int,
    height: int,
    fps: int,
    default_index: int = 0,
    layout_units: Optional[List[TableUnitConfig]] = None,
    enumerate_fn: Optional[Callable[[], List[CameraInfo]]] = None,
) -> Optional[Tuple[int, int, int, int]]:
    dlg = CameraPickDialog(
        parent,
        width=width,
        height=height,
        fps=fps,
        default_index=default_index,
        layout_units=layout_units,
        enumerate_fn=enumerate_fn,
    )
    parent.wait_window(dlg)
    return dlg.result
