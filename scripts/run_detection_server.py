"""
DKUScope Detection Server

Reads camera frames, classifies each grid cell's color,
and broadcasts the state over WebSocket for TouchDesigner to consume.

Usage:
    python scripts/run_detection_server.py
    python scripts/run_detection_server.py --config config/project_config.json --port 8765

TD side:
    Connect a WebSocket DAT to ws://localhost:8765
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from pathlib import Path

from control_station.config_manager import load_config
from control_station.detection_service import GridDetector, MultiTableDetector, open_camera
from control_station.ws_server import StateServer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("detection_server")


async def detection_loop(
    config_path: Path,
    host: str,
    port: int,
    target_fps: float,
) -> None:
    config = load_config(config_path)
    logger.info("Config loaded from %s", config_path)

    multi_mode = config.layout.enabled and len(config.layout.units) > 0
    multi_det = None
    single_det = None
    cap = None

    if multi_mode:
        multi_det = MultiTableDetector(config)
        logger.info("Multi-table mode: %d units, global grid %dx%d", len(config.layout.units), multi_det.total_rows, multi_det.total_cols)
    else:
        single_det = GridDetector(config)
        logger.info("Single-table mode: %dx%d", single_det.rows, single_det.cols)
        cap = open_camera(config)
        logger.info("Camera %d opened at %dx%d@%dfps", config.camera.index, config.camera.width, config.camera.height, config.camera.fps)

    server = StateServer(host=host, port=port)
    server_task = asyncio.create_task(server.start())

    interval = 1.0 / target_fps
    logger.info("Detection running at %.1f Hz, broadcasting on ws://%s:%d", target_fps, host, port)

    try:
        while True:
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

            if result.changed_cells:
                labels = ", ".join(f"({c.row},{c.col})={c.label}" for c in result.changed_cells[:5])
                logger.info("seq=%d changed=%d: %s", result.seq, len(result.changed_cells), labels)

            elapsed = time.monotonic() - t0
            await asyncio.sleep(max(0, interval - elapsed))
    except asyncio.CancelledError:
        pass
    finally:
        if cap:
            cap.release()
        if multi_det:
            multi_det.release()
        server_task.cancel()
        logger.info("Detection server stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="DKUScope Detection + WebSocket Server")
    parser.add_argument(
        "--config", type=Path, default=Path("config/project_config.json"),
        help="Path to project config JSON",
    )
    parser.add_argument("--host", default="0.0.0.0", help="WebSocket bind host")
    parser.add_argument("--port", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--fps", type=float, default=10.0, help="Target detection FPS")
    args = parser.parse_args()

    asyncio.run(detection_loop(args.config, args.host, args.port, args.fps))


if __name__ == "__main__":
    main()
