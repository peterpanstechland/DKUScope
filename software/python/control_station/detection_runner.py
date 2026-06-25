from __future__ import annotations

import asyncio
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .config_schema import ProjectConfig
from .detection_service import CellResult, GridDetector, MultiTableDetector, open_camera
from .ws_server import StateServer

logger = logging.getLogger(__name__)


@dataclass
class DetectionStatus:
    running: bool = False
    seq: int = 0
    changed_count: int = 0
    grid_rows: int = 0
    grid_cols: int = 0
    client_count: int = 0
    ws_url: str = ""
    error: str = ""
    cells: List[CellResult] = field(default_factory=list)
    changed_cells: List[CellResult] = field(default_factory=list)


class DetectionRunner:
    """Background detection + WebSocket broadcast, usable from UI or CLI."""

    def __init__(
        self,
        on_status: Optional[Callable[[DetectionStatus], None]] = None,
    ) -> None:
        self._on_status = on_status
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._status = DetectionStatus()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(
        self,
        config: ProjectConfig,
        host: str = "0.0.0.0",
        port: int = 8765,
        target_fps: float = 10.0,
    ) -> None:
        if self.is_running:
            raise RuntimeError("Detection is already running")
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_thread,
            args=(config, host, port, target_fps),
            daemon=True,
            name="detection-runner",
        )
        self._thread.start()

    def stop(self, timeout: float = 3.0) -> None:
        if not self.is_running:
            return
        self._stop_event.set()
        self._thread.join(timeout=timeout)
        self._thread = None
        self._emit(DetectionStatus(running=False, ws_url=self._status.ws_url))

    def _emit(self, status: DetectionStatus) -> None:
        self._status = status
        if self._on_status:
            self._on_status(status)

    def _run_thread(
        self,
        config: ProjectConfig,
        host: str,
        port: int,
        target_fps: float,
    ) -> None:
        try:
            asyncio.run(self._detection_loop(config, host, port, target_fps))
        except Exception as exc:
            logger.exception("Detection runner failed")
            self._emit(DetectionStatus(running=False, error=str(exc)))

    async def _detection_loop(
        self,
        config: ProjectConfig,
        host: str,
        port: int,
        target_fps: float,
    ) -> None:
        multi_mode = config.layout.enabled and len(config.layout.units) > 0
        multi_det: Optional[MultiTableDetector] = None
        single_det: Optional[GridDetector] = None
        cap = None

        if multi_mode:
            multi_det = MultiTableDetector(config)
            rows, cols = multi_det.total_rows, multi_det.total_cols
            logger.info(
                "Multi-table mode: %d units, global grid %dx%d",
                len(config.layout.units), rows, cols,
            )
        else:
            single_det = GridDetector(config)
            rows, cols = single_det.rows, single_det.cols
            cap = open_camera(config)
            logger.info("Single-table mode: %dx%d", rows, cols)

        ws_url = f"ws://localhost:{port}"
        server = StateServer(host=host, port=port)
        server_task = asyncio.create_task(server.start())
        interval = 1.0 / target_fps

        self._emit(DetectionStatus(
            running=True,
            grid_rows=rows,
            grid_cols=cols,
            ws_url=ws_url,
        ))

        try:
            while not self._stop_event.is_set():
                t0 = time.monotonic()

                if multi_mode and multi_det:
                    result = multi_det.process_all()
                elif single_det and cap:
                    ok, frame = cap.read()
                    if not ok:
                        await asyncio.sleep(0.01)
                        continue
                    result = single_det.process_frame(frame)
                else:
                    await asyncio.sleep(0.1)
                    continue

                await server.broadcast(result)

                self._emit(DetectionStatus(
                    running=True,
                    seq=result.seq,
                    changed_count=len(result.changed_cells),
                    grid_rows=result.rows,
                    grid_cols=result.cols,
                    client_count=len(server._clients),
                    ws_url=ws_url,
                    cells=list(result.cells),
                    changed_cells=list(result.changed_cells),
                ))

                elapsed = time.monotonic() - t0
                await asyncio.sleep(max(0, interval - elapsed))
        finally:
            if cap:
                cap.release()
            if multi_det:
                multi_det.release()
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
            logger.info("Detection runner stopped")
