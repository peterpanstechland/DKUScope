from __future__ import annotations

import socket


def is_port_available(port: int, host: str = "0.0.0.0") -> bool:
    """Return True if the TCP port can be bound (not in use)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False
