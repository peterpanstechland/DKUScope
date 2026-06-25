from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Dict, List, Optional

from .detection_service import CellResult
from .i18n import t


DEFAULT_CLASS_COLORS: Dict[int, str] = {
    0: "#1a1a1a",
    1: "#D73A49",
    2: "#8B5A2B",
    3: "#F2CC0C",
    4: "#2F2F2F",
    5: "#F7A1C4",
    6: "#2EA043",
    7: "#1F6FEB",
    8: "#F5F5F5",
}


class DetectionMonitorWidget(ttk.Frame):
    """Live grid map + merged camera preview + change log."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self._class_colors: Dict[int, str] = dict(DEFAULT_CLASS_COLORS)
        self._cell_px = 48
        self._gap_px = 2
        self._grid_canvas: Optional[tk.Canvas] = None
        self._merged_canvas: Optional[tk.Canvas] = None
        self._merged_photo = None
        self._build_ui()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        self.summary_var = tk.StringVar(value=t("detect_monitor_idle"))
        ttk.Label(self, textvariable=self.summary_var, wraplength=900).grid(
            row=0, column=0, sticky="w", pady=(0, 8),
        )

        compare_frame = ttk.Frame(self)
        compare_frame.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        compare_frame.columnconfigure(0, weight=1)
        compare_frame.columnconfigure(1, weight=1)

        grid_frame = ttk.LabelFrame(compare_frame, text=t("detect_monitor_grid"), padding=8)
        grid_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._grid_host = ttk.Frame(grid_frame)
        self._grid_host.pack()

        merged_frame = ttk.LabelFrame(compare_frame, text=t("detect_monitor_merged"), padding=8)
        merged_frame.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        self._merged_host = ttk.Frame(merged_frame)
        self._merged_host.pack()
        self._merged_placeholder = ttk.Label(
            merged_frame,
            text=t("detect_monitor_merged_idle"),
            foreground="#666",
            wraplength=280,
        )
        self._merged_placeholder.pack(pady=40)

        log_frame = ttk.LabelFrame(self, text=t("detect_monitor_changes"), padding=8)
        log_frame.grid(row=2, column=0, sticky="nsew")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        cols = ("seq", "row", "col", "label", "confidence")
        self.change_tree = ttk.Treeview(log_frame, columns=cols, show="headings", height=10)
        heads = {
            "seq": t("col_detect_seq"),
            "row": t("col_detect_row"),
            "col": t("col_detect_col"),
            "label": t("col_detect_label"),
            "confidence": t("col_detect_conf"),
        }
        for col in cols:
            self.change_tree.heading(col, text=heads[col])
            self.change_tree.column(col, width=90 if col != "label" else 140, anchor="center")
        scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.change_tree.yview)
        self.change_tree.configure(yscrollcommand=scroll.set)
        self.change_tree.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        btn_row = ttk.Frame(self)
        btn_row.grid(row=3, column=0, sticky="e", pady=(8, 0))
        ttk.Button(btn_row, text=t("btn_clear_detect_log"), command=self.clear_log).pack(side=tk.RIGHT)

    def set_class_colors(self, class_id_to_hex: Dict[int, str]) -> None:
        self._class_colors = dict(DEFAULT_CLASS_COLORS)
        self._class_colors.update(class_id_to_hex)

    def clear_log(self) -> None:
        for iid in self.change_tree.get_children():
            self.change_tree.delete(iid)

    def show_idle(self) -> None:
        self.summary_var.set(t("detect_monitor_idle"))
        if self._grid_canvas:
            self._grid_canvas.destroy()
            self._grid_canvas = None
        self._clear_merged_preview()

    def _clear_merged_preview(self) -> None:
        if self._merged_canvas:
            self._merged_canvas.destroy()
            self._merged_canvas = None
        self._merged_photo = None
        self._merged_placeholder.pack(pady=40)

    def update_frame(
        self,
        seq: int,
        rows: int,
        cols: int,
        cells: List[CellResult],
        changed_cells: List[CellResult],
        client_count: int,
        ws_url: str,
        building_count: int = 0,
        coverage: float = 0.0,
        debug_overlay: bool = False,
        merged_preview: Optional[object] = None,
    ) -> None:
        self.summary_var.set(t(
            "detect_monitor_summary",
            seq=seq,
            rows=rows,
            cols=cols,
            changed=len(changed_cells),
            buildings=building_count,
            coverage=coverage,
            clients=client_count,
            url=ws_url,
        ))
        self._draw_grid(rows, cols, cells, debug_overlay=debug_overlay)
        if merged_preview is not None:
            self._show_merged_preview(merged_preview)
        for cell in changed_cells:
            self.change_tree.insert("", 0, values=(
                seq, cell.row, cell.col, cell.label, f"{cell.confidence:.2f}",
            ))
        children = self.change_tree.get_children()
        if len(children) > 200:
            for iid in children[200:]:
                self.change_tree.delete(iid)

    def _draw_grid(
        self,
        rows: int,
        cols: int,
        cells: List[CellResult],
        debug_overlay: bool = False,
    ) -> None:
        if self._grid_canvas:
            self._grid_canvas.destroy()

        w = cols * self._cell_px + self._gap_px
        h = rows * self._cell_px + self._gap_px
        canvas = tk.Canvas(self._grid_host, width=w, height=h, bg="#0d0d0d", highlightthickness=0)
        canvas.pack()

        cell_map: Dict[tuple[int, int], CellResult] = {
            (c.row, c.col): c for c in cells
        }

        for r in range(rows):
            for c in range(cols):
                cell = cell_map.get((r, c))
                class_id = cell.class_id if cell else 0
                fill = self._class_colors.get(class_id, "#333333")
                x0 = c * self._cell_px + self._gap_px
                y0 = r * self._cell_px + self._gap_px
                x1 = (c + 1) * self._cell_px - self._gap_px
                y1 = (r + 1) * self._cell_px - self._gap_px
                canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#222222")
                if cell and cell.class_id > 0:
                    text_color = "#ffffff" if class_id in (1, 2, 4, 6, 7) else "#000000"
                    canvas.create_text(
                        (x0 + x1) / 2, (y0 + y1) / 2,
                        text=str(cell.class_id),
                        fill=text_color,
                        font=("", 9, "bold"),
                    )
                elif debug_overlay and cell:
                    canvas.create_text(
                        (x0 + x1) / 2, (y0 + y1) / 2,
                        text=f"{cell.class_id}\n{cell.confidence:.2f}\n{cell.mask_area_ratio:.0%}",
                        fill="#cccccc",
                        font=("", 7),
                    )

        self._grid_canvas = canvas

    def _show_merged_preview(self, frame) -> None:
        try:
            import cv2
            from PIL import Image, ImageTk
        except ImportError:
            return

        self._merged_placeholder.pack_forget()
        if self._merged_canvas:
            self._merged_canvas.destroy()

        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        max_w, max_h = 480, 260
        scale = min(max_w / w, max_h / h, 1.0)
        nw, nh = int(w * scale), int(h * scale)
        if scale < 1.0:
            rgb = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        img = Image.fromarray(rgb)
        self._merged_photo = ImageTk.PhotoImage(image=img)
        canvas = tk.Canvas(self._merged_host, width=nw, height=nh, bg="#1a1a1a", highlightthickness=0)
        canvas.pack()
        canvas.create_image(0, 0, anchor=tk.NW, image=self._merged_photo)
        self._merged_canvas = canvas
