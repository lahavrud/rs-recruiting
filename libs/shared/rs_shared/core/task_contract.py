"""Typed contract for the SQS task queue — the inter-service wire format.

The API (producer) enqueues work and the worker (consumer) processes it over
SQS using a JSON message of the shape ``{"task": <name>, ...kwargs}``. This
module is the single source of truth for that contract so the two services can
never drift:

- ``TaskName`` — the registry keys (the ``"task"`` field values).
- ``build_*_message(...)`` — construct the exact wire dict for each task,
  including base64 transport-encoding of email attachments.
- ``decode_message(body)`` — the inverse used by the worker: pop the task name
  and decode attachments back to bytes.

The wire format is intentionally plain JSON (not pickled/typed on the wire) so
it stays language-agnostic and stable; the typing here is a producer/consumer
convenience, not part of the bytes. Changing any ``build_*`` shape is a
breaking change to a live queue — keep producer and consumer in lockstep.
"""

from __future__ import annotations

import base64
from typing import Optional, TypedDict, Union

# Recipient may be a single address or a list of them.
Recipients = Union[str, list[str]]
# An attachment in memory: (filename, raw_bytes, mime_type).
Attachment = tuple[str, bytes, str]
# An attachment on the wire: [filename, base64_str, mime_type] (JSON has no bytes).
WireAttachment = list  # [str, str, str]


class TaskName:
    """Registry keys — the value of the message ``"task"`` field.

    These are the dispatch keys in ``TASK_REGISTRY`` (see
    ``rs_shared.core.tasks``). They are plain strings so they serialize as-is.
    """

    # Legacy: carries the whole email payload on the wire. Superseded by
    # SEND_OUTBOX_EMAIL, but kept registered for one release so messages
    # already in flight during the rolling deploy still dispatch (the api and
    # worker ship as separate images — see rules/worker.md). Remove once the
    # queue has drained.
    SEND_EMAIL = "send_email"
    SEND_OUTBOX_EMAIL = "send_outbox_email"
    SWEEP_EMAIL_OUTBOX = "sweep_email_outbox"
    BUILD_DATA_EXPORT = "build_data_export"
    PURGE_EXPIRED_CANDIDATES = "purge_expired_candidates"
    EMBED_JOB = "embed_job"
    MATCH_CANDIDATE = "match_candidate"


# --- Typed message shapes (producer/consumer convenience; not on the wire) ---


class EmailMessage(TypedDict):
    task: str
    to: Recipients
    subject: str
    body: str
    html_body: Optional[str]
    attachments: Optional[list[WireAttachment]]
    from_email: Optional[str]


class SendOutboxEmailMessage(TypedDict):
    task: str
    outbox_id: int


class SweepEmailOutboxMessage(TypedDict):
    task: str


class DataExportMessage(TypedDict):
    task: str
    user_id: int


class EmbedJobMessage(TypedDict):
    task: str
    job_id: int


class MatchCandidateMessage(TypedDict):
    task: str
    candidate_id: int


class PurgeMessage(TypedDict):
    task: str


# --- Attachment transport encoding ---------------------------------------


def encode_attachments(
    attachments: Optional[list[Attachment]],
) -> Optional[list[WireAttachment]]:
    """Base64-encode attachment bytes for JSON transport (or None)."""
    if not attachments:
        return None
    return [
        [name, base64.b64encode(data).decode(), mime]
        for name, data, mime in attachments
    ]


def decode_attachments(
    wire: Optional[list[WireAttachment]],
) -> Optional[list[Attachment]]:
    """Inverse of :func:`encode_attachments` — back to ``(name, bytes, mime)``."""
    if not wire:
        return None
    return [(name, base64.b64decode(data), mime) for name, data, mime in wire]


# --- Message builders (the canonical wire shapes) ------------------------


def build_email_message(
    to: Recipients,
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[list[Attachment]] = None,
    from_email: Optional[str] = None,
) -> EmailMessage:
    return {
        "task": TaskName.SEND_EMAIL,
        "to": to,
        "subject": subject,
        "body": body,
        "html_body": html_body,
        "attachments": encode_attachments(attachments),
        "from_email": from_email,
    }


def build_send_outbox_email_message(outbox_id: int) -> SendOutboxEmailMessage:
    """Nudge the worker to send one outbox row.

    Carries only the row id — the payload (body, html, attachments) lives in
    ``email_outbox``. That keeps the message far under SQS's 256KB ceiling
    regardless of attachment size, and makes the row, not the message, the
    unit of idempotency.
    """
    return {"task": TaskName.SEND_OUTBOX_EMAIL, "outbox_id": outbox_id}


def build_sweep_email_outbox_message() -> SweepEmailOutboxMessage:
    return {"task": TaskName.SWEEP_EMAIL_OUTBOX}


def build_data_export_message(user_id: int) -> DataExportMessage:
    return {"task": TaskName.BUILD_DATA_EXPORT, "user_id": user_id}


def build_embed_job_message(job_id: int) -> EmbedJobMessage:
    return {"task": TaskName.EMBED_JOB, "job_id": job_id}


def build_match_candidate_message(candidate_id: int) -> MatchCandidateMessage:
    return {"task": TaskName.MATCH_CANDIDATE, "candidate_id": candidate_id}


def build_purge_message() -> PurgeMessage:
    return {"task": TaskName.PURGE_EXPIRED_CANDIDATES}


# --- Consumer decode ------------------------------------------------------


def decode_message(body: dict) -> tuple[str, dict]:
    """Split a parsed SQS body into ``(task_name, kwargs)`` for dispatch.

    Pops the ``"task"`` field and decodes any base64 ``attachments`` back to
    ``(name, bytes, mime)`` tuples. The returned kwargs are passed straight to
    the registered task coroutine. Does not mutate the caller's dict.
    """
    body = dict(body)
    task_name = body.pop("task")
    if "attachments" in body and body["attachments"]:
        body["attachments"] = decode_attachments(body["attachments"])
    return task_name, body
