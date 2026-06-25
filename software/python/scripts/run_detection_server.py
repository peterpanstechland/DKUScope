"""
DKUScope Detection Server (headless CLI)

Same logic as the integrated control station "Start Detection" button.
Use this when you only need detection + WebSocket without the UI.

Usage:
    python scripts/run_detection_server.py
    python scripts/run_detection_server.py --config config/project_config.json --port 8765
"""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from control_station.config_manager import load_config
from control_station.detection_runner import DetectionRunner, DetectionStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("detection_server")


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

    config = load_config(args.config)
    logger.info("Config loaded from %s", args.config)

    def on_status(status: DetectionStatus) -> None:
        if status.error:
            logger.error("%s", status.error)
        elif status.running and status.seq % 10 == 0:
            logger.info(
                "seq=%d grid=%dx%d clients=%d %s",
                status.seq, status.grid_rows, status.grid_cols,
                status.client_count, status.ws_url,
            )

    runner = DetectionRunner(on_status=on_status)
    runner.start(config, host=args.host, port=args.port, target_fps=args.fps)
    logger.info("Press Ctrl+C to stop")

    try:
        while runner.is_running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()
        logger.info("Detection server stopped.")


if __name__ == "__main__":
    main()
