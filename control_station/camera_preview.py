from __future__ import annotations

import threading
import tkinter as tk
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

from .i18n import t


class CameraPreviewWidget(tk.LabelFrame):
    """Embeddable live camera preview widget for tkinter."""

    def __init__(
        self,
        parent: tk.Widget,
        preview_width: int = 420,
        preview_height: int = 315,
        **kwargs,
    ) -> None:
        super().__init__(parent, text=t("preview_title"), **kwargs)

        self.preview_width = preview_width
        self.preview_height = preview_height

        self._cap: Optional[cv2.VideoCapture] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._photo: Optional[ImageTk.PhotoImage] = None

        self._canvas = tk.Canvas(self, width=preview_width, height=preview_height, bg="#1a1a1a")
        self._canvas.pack(padx=4, pady=4)

        self._info_var = tk.StringVar(value=t("preview_disconnected"))
        tk.Label(self, textvariable=self._info_var, anchor="w").pack(fill=tk.X, padx=4)

        btn_frame = tk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=4, pady=(0, 4))
        tk.Button(btn_frame, text=t("preview_start"), command=self.start_request).pack(side=tk.LEFT, padx=2)
        tk.Button(btn_frame, text=t("preview_stop"), command=self.stop).pack(side=tk.LEFT, padx=2)

        self._camera_index = 0
        self._cam_width = 640
        self._cam_height = 480
        self._cam_fps = 30

        self._show_grid = False
        self._grid_rows = 16
        self._grid_cols = 16

        self._start_callback = None

    def configure_camera(
        self, index: int, width: int, height: int, fps: int
    ) -> None:
        self._camera_index = index
        self._cam_width = width
        self._cam_height = height
        self._cam_fps = fps

    def configure_grid_overlay(
        self, show: bool, rows: int = 16, cols: int = 16
    ) -> None:
        self._show_grid = show
        self._grid_rows = rows
        self._grid_cols = cols

    def set_start_callback(self, callback) -> None:
        self._start_callback = callback

    def start_request(self) -> None:
        if self._start_callback:
            self._start_callback()
        self.start()

    def start(self) -> None:
        if self._running:
            return
        self._cap = cv2.VideoCapture(self._camera_index, cv2.CAP_DSHOW)
        if not self._cap.isOpened():
            self._info_var.set(t("preview_cam_fail", idx=self._camera_index))
            self._cap.release()
            self._cap = None
            return
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._cam_width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._cam_height)
        self._cap.set(cv2.CAP_PROP_FPS, self._cam_fps)
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        self._info_var.set(t("preview_cam_ok", idx=self._camera_index))

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        if self._cap:
            self._cap.release()
            self._cap = None
        self._info_var.set(t("preview_stopped"))

    def _capture_loop(self) -> None:
        while self._running and self._cap and self._cap.isOpened():
            ok, frame = self._cap.read()
            if not ok:
                continue
            if self._show_grid:
                frame = self._draw_grid(frame)
            self._update_canvas(frame)

    def _draw_grid(self, frame: np.ndarray) -> np.ndarray:
        h, w = frame.shape[:2]
        cell_h = h / self._grid_rows
        cell_w = w / self._grid_cols
        for r in range(1, self._grid_rows):
            y = int(r * cell_h)
            cv2.line(frame, (0, y), (w, y), (80, 80, 80), 1)
        for c in range(1, self._grid_cols):
            x = int(c * cell_w)
            cv2.line(frame, (x, 0), (x, h), (80, 80, 80), 1)
        return frame

    def _update_canvas(self, frame: np.ndarray) -> None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        img = img.resize(
            (self.preview_width, self.preview_height), Image.LANCZOS
        )
        self._photo = ImageTk.PhotoImage(image=img)
        self._canvas.create_image(0, 0, anchor=tk.NW, image=self._photo)

    def destroy(self) -> None:
        self.stop()
        super().destroy()
