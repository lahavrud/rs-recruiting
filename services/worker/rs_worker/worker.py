"""SQS worker — polls the task queue and dispatches to registered task functions.

Entry point:
    python -m rs_worker.worker

Message format (JSON):
    {"task": "<registry_key>", ...kwargs}

The worker handles SIGTERM gracefully: it finishes the current batch then exits.
Visibility timeout matches the maximum task duration (300 s) so a task that is
still running when its visibility expires gets redelivered to the DLQ rather
than running twice.
"""

import asyncio
import json
import logging
import signal
import sys

import aioboto3
from opentelemetry import trace as otel_trace
from pythonjsonlogger import json as jsonlogger

from rs_shared.core.infrastructure.config import settings
from rs_shared.core.infrastructure.request_context import RequestIdFilter
from rs_shared.core.infrastructure.telemetry import (
    configure_telemetry,
    shutdown_telemetry,
)
from rs_shared.core.task_contract import TaskName, decode_message
from rs_shared.core.tasks import TASK_REGISTRY

logger = logging.getLogger(__name__)

_VISIBILITY_TIMEOUT = 300  # seconds — must match job_timeout in infra config
_LONG_POLL_SECONDS = 20
_MAX_MESSAGES = 10

# Tasks that hit the email provider, and so must be paced by
# settings.email_send_delay_seconds. Both entries are load-bearing: nothing
# produces SEND_EMAIL any more, but in-flight messages still drain through it
# for one release, and every new send arrives as SEND_OUTBOX_EMAIL. Missing the
# latter would leave the provider's rate limit unguarded on 100% of email —
# including the bursts from a job close (one row per application) and from a
# sweeper pass (up to 100 re-enqueued rows).
_EMAIL_TASKS = frozenset({TaskName.SEND_EMAIL, TaskName.SEND_OUTBOX_EMAIL})


_tracer = otel_trace.get_tracer("rs_worker.worker")


def _configure_logging() -> None:
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(otelTraceID)s %(otelSpanID)s %(message)s",  # noqa: E501
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)


async def _process_message(raw_body: str) -> str:
    body = json.loads(raw_body)
    task_name, kwargs = decode_message(body)

    fn = TASK_REGISTRY.get(task_name)
    if fn is None:
        logger.warning("unknown_task", extra={"task": task_name})
        return task_name

    with _tracer.start_as_current_span(
        f"worker.task.{task_name}",
        attributes={"worker.task_name": task_name},
    ) as span:
        logger.info("task_start", extra={"task": task_name})
        try:
            await fn(**kwargs)
            logger.info("task_done", extra={"task": task_name})
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(otel_trace.StatusCode.ERROR, str(exc))
            raise
    return task_name


async def run(stop_event: asyncio.Event) -> None:
    if not settings.sqs_queue_url:
        logger.error("SQS_QUEUE_URL is not configured — worker cannot start")
        sys.exit(1)

    logger.info("worker_starting", extra={"queue": settings.sqs_queue_url})

    session = aioboto3.Session()
    async with session.client(
        "sqs",
        region_name=settings.aws_region,
        endpoint_url=settings.sqs_endpoint_url,
    ) as sqs:
        while not stop_event.is_set():
            resp = await sqs.receive_message(
                QueueUrl=settings.sqs_queue_url,
                MaxNumberOfMessages=_MAX_MESSAGES,
                WaitTimeSeconds=_LONG_POLL_SECONDS,
                VisibilityTimeout=_VISIBILITY_TIMEOUT,
            )
            for msg in resp.get("Messages", []):
                receipt = msg["ReceiptHandle"]
                try:
                    task_name = await _process_message(msg["Body"])
                    await sqs.delete_message(
                        QueueUrl=settings.sqs_queue_url,
                        ReceiptHandle=receipt,
                    )
                    delay = settings.email_send_delay_seconds
                    if task_name in _EMAIL_TASKS and delay > 0:
                        await asyncio.sleep(delay)
                except Exception:
                    logger.exception(
                        "task_failed",
                        extra={"receipt_prefix": receipt[:20]},
                    )
                    # Do NOT delete — SQS redelivers after visibility timeout.
                    # The DLQ captures messages that exceed max receive count.

    logger.info("worker_stopped")


def main() -> None:
    _configure_logging()
    configure_telemetry("rs-recruiting-worker")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    stop_event = asyncio.Event()

    def _handle_sigterm(*_) -> None:
        logger.info("worker_shutting_down")
        loop.call_soon_threadsafe(stop_event.set)

    signal.signal(signal.SIGTERM, _handle_sigterm)
    signal.signal(signal.SIGINT, _handle_sigterm)

    try:
        loop.run_until_complete(run(stop_event))
    finally:
        shutdown_telemetry()
        loop.close()


if __name__ == "__main__":
    main()
