from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from listener.client import SolanaLogsClient
from listener.config import Settings
from listener.dedupe import LRUDeduper
from listener.logging_r import get_logger
from listener.models import PumpFunEvent
from listener.parser import HeuristicLogParser, PumpFunParser, event_identity

log = get_logger(__name__)


class ListenerPipeline:
    def __init__(
        self,
        settings: Settings,
        parser: PumpFunParser | None = None,
        client: SolanaLogsClient | None = None,
    ) -> None:
        self._settings = settings
        self._parser = parser or HeuristicLogParser()
        self._client = client or SolanaLogsClient(settings)
        self._event_dedupe = LRUDeduper(settings.dedupe_capacity)
        self._stats = {"received": 0, "emitted": 0, "duplicates": 0, "parse_errors": 0, "dropped": 0}

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    @asynccontextmanager
    async def run(self) -> AsyncIterator[AsyncIterator[PumpFunEvent]]:
        queue: asyncio.Queue[PumpFunEvent | None] = asyncio.Queue(
            maxsize=self._settings.queue_max_size
        )

        async def feeder() -> None:
            try:
                async with self._client.stream() as raw_stream:
                    async for notification in raw_stream:
                        self._stats["received"] += 1

                        try:
                            event = self._parser.parse(
                                notification, self._settings.pumpfun_program_id
                            )
                        except Exception as exc:
                            self._stats["parse_errors"] += 1
                            log.warning(
                                "parse_error",
                                signature=notification.signature,
                                error=str(exc),
                            )
                            continue

                        if not self._event_dedupe.add(event_identity(event)):
                            self._stats["duplicates"] += 1
                            continue

                        try:
                            queue.put_nowait(event)
                        except asyncio.QueueFull:
                            self._stats["dropped"] = self._stats.get("dropped", 0) + 1
                            log.warning(
                                "queue_full_dropping",
                                signature=event.signature,
                                queue_size=queue.qsize(),
                            )
                        else:
                            self._stats["emitted"] += 1
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("feeder_crashed", error=str(exc), error_type=type(exc).__name__)
            finally:
                await queue.put(None)

        async def consumer() -> AsyncIterator[PumpFunEvent]:
            while True:
                item = await queue.get()
                if item is None:
                    return
                yield item

        feeder_task = asyncio.create_task(feeder(), name="listener-feeder")
        try:
            yield consumer()
        finally:
            feeder_task.cancel()
            try:
                await feeder_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.warning("feeder_task_error", error=str(exc), error_type=type(exc).__name__)