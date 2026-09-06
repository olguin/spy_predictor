"""Read-only IB Gateway connectivity probe.

This module intentionally requests only IBKR server time. It does not import,
construct, or submit orders and does not request account information.
"""

from __future__ import annotations

import json
import os
import sys
import threading
from datetime import datetime, timezone

import ibapi
from spy_predictor_quant.ibkr_config import GatewayConfig
from spy_predictor_quant.ibkr_session import IbkrSession


class GatewayProbe(IbkrSession):
    def __init__(self, config: GatewayConfig) -> None:
        super().__init__(config)
        self.server_time_received = threading.Event()
        self.server_time: int | None = None

    def currentTime(self, time: int) -> None:  # noqa: N802 - IBKR callback
        self.server_time = time
        self.server_time_received.set()

def run_probe(timeout_seconds: float = 10.0) -> dict[str, object]:
    config = GatewayConfig.from_environment(os.environ)
    probe = GatewayProbe(config)

    try:
        probe.connect_and_start(timeout_seconds)

        probe.reqCurrentTime()
        if not probe.server_time_received.wait(timeout_seconds):
            raise TimeoutError("IB Gateway did not return server time")

        if probe.server_time is None:
            raise RuntimeError("IB Gateway returned an invalid server time")

        connection_time = probe.twsConnectionTime()
        if isinstance(connection_time, bytes):
            connection_time = connection_time.decode("utf-8", errors="replace")

        return {
            "status": "ok",
            "mode": "paper",
            "readOnlyClient": True,
            "host": config.host,
            "port": config.port,
            "clientId": config.client_id,
            "ibapiVersion": ibapi.__version__,
            "serverVersion": probe.serverVersion(),
            "connectionTime": connection_time,
            "serverTime": datetime.fromtimestamp(
                probe.server_time, timezone.utc
            ).isoformat(),
            "informationalCodes": sorted(
                {int(warning["code"]) for warning in probe.warnings}
            ),
        }
    finally:
        probe.close()


def main() -> int:
    try:
        result = run_probe()
    except Exception as error:  # boundary converts SDK failures to CLI output
        print(
            json.dumps(
                {"status": "error", "message": str(error)},
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
