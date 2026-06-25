from __future__ import annotations

import asyncio
import json
from dataclasses import asdict
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

from .detection_service import FrameResult
from .log_service import get_logger
from .reconstruction_service import WorldState, world_state_to_dict

logger = get_logger("websocket")


class StateServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: Set[WebSocketServerProtocol] = set()
        self._latest_frame: str = "{}"
        self._server = None

    async def open(self) -> None:
        if self._server is not None:
            return
        self._server = await websockets.serve(
            self._handler,
            self.host,
            self.port,
            reuse_address=True,
        )
        logger.info("WebSocket server listening on ws://%s:%s", self.host, self.port)

    async def close(self) -> None:
        if self._server is None:
            return
        self._server.close()
        await self._server.wait_closed()
        self._server = None
        logger.info("WebSocket server closed on port %s", self.port)

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        self._clients.add(ws)
        remote = ws.remote_address
        logger.info("Client connected: %s", remote)
        try:
            await ws.send(self._latest_frame)
            async for _msg in ws:
                pass
        finally:
            self._clients.discard(ws)
            logger.info("Client disconnected: %s", remote)

    async def broadcast_frame_state(self, result: FrameResult) -> None:
        payload = json.dumps(
            {
                "type": "frame_state",
                "seq": result.seq,
                "timestamp_ms": result.timestamp_ms,
                "grid": {
                    "rows": result.rows,
                    "cols": result.cols,
                    "cells": [asdict(c) for c in result.cells],
                },
                "changed_count": len(result.changed_cells),
                "changed": [asdict(c) for c in result.changed_cells],
            },
            ensure_ascii=False,
        )
        self._latest_frame = payload
        await self._broadcast_raw(payload)

    async def broadcast(self, result: FrameResult) -> None:
        """Backward-compatible alias for broadcast_frame_state."""
        await self.broadcast_frame_state(result)

    async def broadcast_world_state(self, world: WorldState) -> None:
        payload = json.dumps(world_state_to_dict(world), ensure_ascii=False)
        await self._broadcast_raw(payload)

    async def broadcast_health(
        self,
        seq: int,
        timestamp_ms: int,
        capture_ms: float | None = None,
        processing_ms: float | None = None,
    ) -> None:
        payload = json.dumps(
            {
                "type": "health",
                "seq": seq,
                "timestamp_ms": timestamp_ms,
                "capture_ms": capture_ms,
                "processing_ms": processing_ms,
            },
            ensure_ascii=False,
        )
        await self._broadcast_raw(payload)

    async def _broadcast_raw(self, payload: str) -> None:
        if self._clients:
            await asyncio.gather(
                *[self._safe_send(ws, payload) for ws in self._clients.copy()],
                return_exceptions=True,
            )

    async def _safe_send(self, ws: WebSocketServerProtocol, data: str) -> None:
        try:
            await ws.send(data)
        except websockets.ConnectionClosed:
            self._clients.discard(ws)

    async def start(self) -> None:
        """Open the server and block until it is closed."""
        await self.open()
        assert self._server is not None
        await self._server.wait_closed()
