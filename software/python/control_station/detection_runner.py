from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .background_refs import load_background_refs
from .config_schema import ProjectConfig
from .detection_service import CellResult, GridDetector, MultiTableDetector, open_camera
from .i18n import t
from .net_utils import is_port_available
from .reconstruction_service import reconstruct_world_state
from .log_service import get_logger
from .ws_server import StateServer

logger = get_logger("detection")


@dataclass
class DetectionStatus:
    running: bool = False
    seq: int = 0
    changed_count: int = 0
    building_count: int = 0
    grid_rows: int = 0
    grid_cols: int = 0
    client_count: int = 0
    ws_url: str = ""
    error: str = ""
    cells: List[CellResult] = field(default_factory=list)
    changed_cells: List[CellResult] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    processing_ms: float = 0.0
    debug_frame: Optional[object] = None
    merged_preview: Optional[object] = None


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
        if not is_port_available(port, host):
            raise RuntimeError(t("dlg_port_in_use", port=port))
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
        except OSError as exc:
            winerr = getattr(exc, "winerror", None)
            if winerr == 10048 or exc.errno in (10048, 98):
                self._emit(DetectionStatus(running=False, error=t("dlg_port_in_use", port=port)))
            else:
                logger.exception("Detection runner failed")
                self._emit(DetectionStatus(running=False, error=str(exc)))
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

        ws_url = f"ws://localhost:{port}"
        server = StateServer(host=host, port=port)

        try:
            await server.open()
        except OSError as exc:
            winerr = getattr(exc, "winerror", None)
            if winerr == 10048 or exc.errno in (10048, 98):
                self._emit(DetectionStatus(running=False, error=t("dlg_port_in_use", port=port)))
                return
            raise

        try:
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

            if config.detection.enabled:
                refs = load_background_refs()
                has_ref = bool(refs.get("global") or any(
                    refs.get(u.unit_id) for u in config.layout.units
                ))
                if not has_ref:
                    logger.warning(
                        "Enhanced detection enabled but no background reference captured. "
                        "Empty-cell detection will be less accurate.",
                    )

            interval = 1.0 / target_fps

            self._emit(DetectionStatus(
                running=True,
                grid_rows=rows,
                grid_cols=cols,
                ws_url=ws_url,
            ))

            while not self._stop_event.is_set():
                loop_start = time.perf_counter()
                capture_ms: Optional[float] = None

                if multi_mode and multi_det:
                    process_start = time.perf_counter()
                    result = multi_det.process_all()
                    processing_ms = (time.perf_counter() - process_start) * 1000.0
                elif single_det and cap:
                    capture_start = time.perf_counter()
                    ok, frame = cap.read()
                    capture_ms = (time.perf_counter() - capture_start) * 1000.0
                    if not ok:
                        await asyncio.sleep(0.01)
                        continue
                    process_start = time.perf_counter()
                    result = single_det.process_frame(frame)
                    processing_ms = (time.perf_counter() - process_start) * 1000.0
                else:
                    await asyncio.sleep(0.1)
                    continue

                world = reconstruct_world_state(result, config)

                await server.broadcast_frame_state(result)
                await server.broadcast_world_state(world)
                await server.broadcast_health(
                    seq=result.seq,
                    timestamp_ms=result.timestamp_ms,
                    capture_ms=round(capture_ms, 3) if capture_ms is not None else None,
                    processing_ms=round(processing_ms, 3),
                )

                self._emit(DetectionStatus(
                    running=True,
                    seq=result.seq,
                    changed_count=len(result.changed_cells),
                    building_count=len(world.buildings),
                    grid_rows=result.rows,
                    grid_cols=result.cols,
                    client_count=len(server._clients),
                    ws_url=ws_url,
                    cells=list(result.cells),
                    changed_cells=list(result.changed_cells),
                    metrics=world.metrics,
                    processing_ms=round(processing_ms, 3),
                    debug_frame=result.debug_frame,
                    merged_preview=result.merged_preview,
                ))

                elapsed = time.monotonic() - loop_start
                await asyncio.sleep(max(0, interval - elapsed))
        finally:
            if cap:
                cap.release()
            if multi_det:
                multi_det.release()
            await server.close()
            logger.info("Detection runner stopped")
