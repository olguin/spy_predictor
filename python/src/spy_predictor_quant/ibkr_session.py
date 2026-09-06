"""Reusable, read-only session boundary for the official IBKR Python API."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Self

from ibapi.client import EClient
from ibapi.wrapper import EWrapper

from spy_predictor_quant.ibkr_config import GatewayConfig


INFORMATIONAL_CODES = {1102, 2104, 2106, 2107, 2108, 2158, 2188}


class IbkrRequestError(RuntimeError):
    """Raised when IBKR rejects a specific API request."""

    def __init__(self, message: str, errors: list[dict[str, object]]) -> None:
        super().__init__(message)
        self.errors = errors


@dataclass
class _RequestState:
    completed: threading.Event = field(default_factory=threading.Event)
    errors: list[dict[str, object]] = field(default_factory=list)


class IbkrSession(EWrapper, EClient):
    """Own the IBKR network loop and correlate finite request/response calls."""

    def __init__(self, config: GatewayConfig) -> None:
        EWrapper.__init__(self)
        EClient.__init__(self, self)
        self.config = config
        self.ready = threading.Event()
        self.closed = threading.Event()
        self.warnings: list[dict[str, object]] = []
        self.errors: list[dict[str, object]] = []
        self._network_thread: threading.Thread | None = None
        self._request_lock = threading.Lock()
        self._request_states: dict[int, _RequestState] = {}
        self._next_request_id = 1
        self._closing = False

    def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IBKR callback
        # The callback is IBKR's API-ready signal. The order ID is deliberately
        # ignored because this session exposes market-data operations only.
        self.ready.set()

    def error(  # noqa: N802 - IBKR callback
        self,
        reqId: int,
        errorTime: int,
        errorCode: int,
        errorString: str,
        advancedOrderRejectJson: str = "",
    ) -> None:
        event: dict[str, object] = {
            "requestId": reqId,
            "code": errorCode,
            "message": errorString,
        }
        if errorCode in INFORMATIONAL_CODES:
            self.warnings.append(event)
            return

        self.errors.append(event)
        with self._request_lock:
            if reqId in self._request_states:
                state = self._request_states[reqId]
                state.errors.append(event)
                state.completed.set()
            elif reqId < 0:
                for state in self._request_states.values():
                    state.errors.append(event)
                    state.completed.set()

    def connectionClosed(self) -> None:  # noqa: N802 - IBKR callback
        self.closed.set()
        if self._closing:
            return
        event: dict[str, object] = {
            "requestId": -1,
            "code": 504,
            "message": "IB Gateway closed the API connection",
        }
        self.errors.append(event)
        with self._request_lock:
            for state in self._request_states.values():
                state.errors.append(event)
                state.completed.set()

    def connect_and_start(self, timeout_seconds: float = 10.0) -> Self:
        self.connect(
            self.config.host,
            self.config.port,
            self.config.client_id,
        )
        if not self.isConnected():
            detail = self.errors[-1]["message"] if self.errors else "no SDK detail"
            raise ConnectionError(
                f"Could not connect to IB Gateway at {self.config.host}:"
                f"{self.config.port}: {detail}"
            )

        self._network_thread = threading.Thread(
            target=self.run,
            name="ibkr-api-network-loop",
            daemon=True,
        )
        self._network_thread.start()
        if not self.ready.wait(timeout_seconds):
            self.close()
            detail = self.errors[-1]["message"] if self.errors else "no SDK detail"
            raise TimeoutError(
                f"IB Gateway did not signal API readiness: {detail}"
            )
        return self

    def begin_request(self) -> int:
        if not self.isConnected() or not self.ready.is_set():
            raise ConnectionError("IBKR session is not ready")
        with self._request_lock:
            request_id = self._next_request_id
            self._next_request_id += 1
            self._request_states[request_id] = _RequestState()
        return request_id

    def complete_request(self, request_id: int) -> None:
        with self._request_lock:
            state = self._request_states.get(request_id)
            if state is not None:
                state.completed.set()

    def discard_request(self, request_id: int) -> None:
        with self._request_lock:
            self._request_states.pop(request_id, None)

    def wait_for_request(
        self,
        request_id: int,
        operation: str,
        timeout_seconds: float,
    ) -> None:
        with self._request_lock:
            state = self._request_states.get(request_id)
        if state is None:
            raise RuntimeError(f"Unknown IBKR request ID {request_id}")

        if not state.completed.wait(timeout_seconds):
            with self._request_lock:
                self._request_states.pop(request_id, None)
            raise TimeoutError(
                f"Timed out after {timeout_seconds:g}s waiting for {operation}"
            )

        with self._request_lock:
            completed_state = self._request_states.pop(request_id)
        if completed_state.errors:
            details = "; ".join(
                f"{error['code']}: {error['message']}"
                for error in completed_state.errors
            )
            raise IbkrRequestError(
                f"IBKR rejected {operation}: {details}",
                completed_state.errors,
            )

    def close(self) -> None:
        self._closing = True
        if self.isConnected():
            self.disconnect()
        if (
            self._network_thread is not None
            and self._network_thread is not threading.current_thread()
        ):
            self._network_thread.join(timeout=2.0)

    def __enter__(self) -> Self:
        return self.connect_and_start()

    def __exit__(self, exception_type: object, exception: object, traceback: object) -> None:
        self.close()
