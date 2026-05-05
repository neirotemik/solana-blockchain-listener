from __future__ import annotations

import asyncio
import signal
import sys

import orjson

from listener.config import Settings
from listener.logging_r import configure_logging, get_logger
from listener.pipeline import ListenerPipeline
from collections.abc import AsyncIterator
from listener.models import PumpFunEvent

import structlog

async def _run() -> int:
    settings = Settings()
    configure_logging(level=settings.log_level, json_output=settings.log_json)
    log = get_logger("listener.runner")

    log.info(
        "listener_starting",
        program_id=settings.pumpfun_program_id,
        commitment=settings.commitment,
        queue_max_size=settings.queue_max_size,
    )

    pipeline = ListenerPipeline(settings)
    shutdown = asyncio.Event()

    loop = asyncio.get_running_loop()

    def _request_shutdown() -> None:
        if not shutdown.is_set():
            log.info("shutdown_signal_received")
            shutdown.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_shutdown)
        except NotImplementedError:
            pass

    async with pipeline.run() as events:
        consumer_task = asyncio.create_task(_consume(events, log), name="listener-consumer")
        shutdown_task = asyncio.create_task(shutdown.wait(), name="listener-shutdown")

        done, pending = await asyncio.wait(
            {consumer_task, shutdown_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception as exc:
                log.warning("pending_task_error", task=task.get_name(), error=str(exc))

        for task in done:
            exc = task.exception() if not task.cancelled() else None
            if exc is not None:
                log.error("task_error", task=task.get_name(), error=str(exc))

    log.info("listener_stopped", stats=pipeline.stats)
    return 0

async def _consume(events: AsyncIterator[PumpFunEvent], log: structlog.stdlib.BoundLogger) -> None:  # type: ignore[no-untyped-def]
    async for event in events:
        sys.stdout.buffer.write(orjson.dumps(event.model_dump(mode="json")) + b"\n")
        sys.stdout.buffer.flush()
        log.debug("event_emitted", event_type=event.event_type, signature=event.signature)


def main() -> None:
    try:
        import uvloop  # type: ignore[import-not-found]

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        pass

    try:
        exit_code = asyncio.run(_run())
    except KeyboardInterrupt:
        exit_code = 0
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
