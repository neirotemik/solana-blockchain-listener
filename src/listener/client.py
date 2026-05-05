from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import orjson
import websockets
from websockets.client import WebSocketClientProtocol

from listener.config import Settings
from listener.logging_r import get_logger
from listener.models import RawLogNotification

log = get_logger(__name__)


class SolanaLogsClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sub_id: int | None = None
        self._req_id = 0

    def _next_request_id(self) -> int:
        self._req_id += 1
        return self._req_id

    async def _subscribe(self, ws: WebSocketClientProtocol) -> list[dict]:
        request_id = self._next_request_id()
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "logsSubscribe",
            "params": [
                {"mentions": [self._settings.pumpfun_program_id]},
                {"commitment": self._settings.commitment},
            ],
        }
        await ws.send(orjson.dumps(payload).decode())

        early: list[dict] = []
        while True:
            raw = await ws.recv()
            msg = orjson.loads(raw)
            if msg.get("id") == request_id:
                if "error" in msg:
                    raise RuntimeError(f"logsSubscribe failed: {msg['error']}")
                self._sub_id = msg.get("result")
                log.info(
                    "subscribed",
                    program_id=self._settings.pumpfun_program_id,
                    commitment=self._settings.commitment,
                    subscription_id=self._sub_id,
                )
                return early
            if msg.get("method") == "logsNotification":
                early.append(msg)

    @staticmethod
    def _parse_notification(msg: dict) -> RawLogNotification | None:
        if msg.get("method") != "logsNotification":
            return None
        params = msg.get("params") or {}
        result = params.get("result") or {}
        context = result.get("context") or {}
        value = result.get("value") or {}

        signature = value.get("signature")
        if not signature:
            return None

        return RawLogNotification(
            signature=signature,
            slot=context.get("slot"),
            err=value.get("err"),
            logs=tuple(value.get("logs") or ()),
        )

    async def _stream_once(self) -> AsyncIterator[RawLogNotification]:
        async with websockets.connect(
            self._settings.rpc_ws_url,
            ping_interval=self._settings.ws_ping_interval,
            ping_timeout=self._settings.ws_ping_timeout,
            open_timeout=self._settings.ws_open_timeout,
            max_size=self._settings.ws_max_message_size,
            close_timeout=5.0,
        ) as ws:
            early = await self._subscribe(ws)
            for msg in early:
                notification = self._parse_notification(msg)
                if notification is not None:
                    yield notification
            async for raw in ws:
                try:
                    msg = orjson.loads(raw)
                except ValueError:
                    log.warning("invalid_json_from_ws")
                    continue

                notification = self._parse_notification(msg)
                if notification is not None:
                    yield notification

    @asynccontextmanager
    async def stream(self) -> AsyncIterator[AsyncIterator[RawLogNotification]]:
        queue: asyncio.Queue[RawLogNotification | None] = asyncio.Queue(maxsize=1024)
        stop = asyncio.Event()

        async def producer() -> None:
            delay = self._settings.reconnect_initial_delay
            while not stop.is_set():
                try:
                    log.info("ws_connecting", url=self._redacted_ws_url())
                    async for notification in self._stream_once():
                        if stop.is_set():
                            break
                        await queue.put(notification)
                    delay = self._settings.reconnect_initial_delay
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    log.warning(
                        "ws_disconnect",
                        error=str(exc),
                        error_type=type(exc).__name__,
                        retry_in=round(delay, 2),
                    )
                    try:
                        await asyncio.wait_for(stop.wait(), timeout=delay)
                        break
                    except asyncio.TimeoutError:
                        pass
                    delay = min(
                        self._settings.reconnect_max_delay,
                        max(
                            self._settings.reconnect_initial_delay,
                            delay * self._settings.reconnect_factor,
                        )
                        * (0.8 + 0.4 * random.random()),
                    )
            await queue.put(None)

        async def consumer() -> AsyncIterator[RawLogNotification]:
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item

        producer_task = asyncio.create_task(producer(), name="solana-ws-producer")
        try:
            yield consumer()
        finally:
            stop.set()
            producer_task.cancel()
            try:
                await producer_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.warning("producer_task_error", error=str(exc), error_type=type(exc).__name__)

    def _redacted_ws_url(self) -> str:
        url = self._settings.rpc_ws_url
        if "?" in url:
            return url.split("?", 1)[0] + "?<redacted>"
        return url
