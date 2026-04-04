from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Set

import websockets
from websockets.server import WebSocketServerProtocol

from .detection_service import FrameResult
from .reconstruction_service import WorldState, world_state_to_dict

logger = logging.getLogger(__name__)


class StateServer:
    def __init__(self, host: str = "0.0.0.0", port: int = 8765) -> None:
        self.host = host
        self.port = port
        self._clients: Set[WebSocketServerProtocol] = set()
        self._latest: str = "{}"

    async def _handler(self, ws: WebSocketServerProtocol) -> None:
        self._clients.add(ws)
        remote = ws.remote_address
        logger.info("Client connected: %s", remote)
        try:
            await ws.send(self._latest)
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
        self._latest = payload
        await self._broadcast_raw(payload)

    async def broadcast_world_state(self, world: WorldState) -> None:
        payload = json.dumps(world_state_to_dict(world), ensure_ascii=False)
        self._latest = payload
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
        self._latest = payload
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
        server = await websockets.serve(self._handler, self.host, self.port)
        logger.info("WebSocket server listening on ws://%s:%s", self.host, self.port)
        await server.wait_closed()