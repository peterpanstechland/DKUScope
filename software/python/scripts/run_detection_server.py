"""
DKUScope Detection Server

Reads camera frames, classifies each grid cell's color,
reconstructs building-level state, and broadcasts the state over WebSocket
for TouchDesigner to consume.

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
from control_station.reconstruction_service import reconstruct_world_state
from control_station.ws_server import StateServer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def run_server(config_path: Path, port: int) -> None:
    config = load_config(config_path)
    server = StateServer(port=port)

    if config.layout.enabled and config.layout.units:
        logger.info("Using multi-table detector")
        detector = MultiTableDetector(config)
        cap = None
    else:
        logger.info("Using single-table detector")
        detector = GridDetector(config)
        cap = open_camera(config)

    ws_task = asyncio.create_task(server.start())

    try:
        while True:
            loop_start = time.perf_counter()

            if cap is not None:
                capture_start = time.perf_counter()
                ok, frame = cap.read()
                capture_ms = (time.perf_counter() - capture_start) * 1000.0

                if not ok:
                    logger.warning("Failed to read frame from camera")
                    await asyncio.sleep(0.05)
                    continue

                process_start = time.perf_counter()
                frame_result = detector.process_frame(frame)
                processing_ms = (time.perf_counter() - process_start) * 1000.0
            else:
                capture_ms = None
                process_start = time.perf_counter()
                frame_result = detector.process_all()
                processing_ms = (time.perf_counter() - process_start) * 1000.0

            world_state = reconstruct_world_state(frame_result, config)

            await server.broadcast_frame_state(frame_result)
            await server.broadcast_world_state(world_state)
            await server.broadcast_health(
                seq=frame_result.seq,
                timestamp_ms=frame_result.timestamp_ms,
                capture_ms=round(capture_ms, 3) if capture_ms is not None else None,
                processing_ms=round(processing_ms, 3),
            )

            elapsed = time.perf_counter() - loop_start
            sleep_s = max(0.0, 0.03 - elapsed)   # ~30 FPS target
            await asyncio.sleep(sleep_s)

    except asyncio.CancelledError:
        raise
    except KeyboardInterrupt:
        logger.info("Detection server stopped by user")
    finally:
        if cap is not None:
            cap.release()
        elif hasattr(detector, "release"):
            detector.release()

        ws_task.cancel()
        try:
            await ws_task
        except asyncio.CancelledError:
            pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DKUScope detection server")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/project_config.json"),
        help="Path to project config JSON",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="WebSocket port",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    asyncio.run(run_server(config_path=args.config, port=args.port))


if __name__ == "__main__":
    main()