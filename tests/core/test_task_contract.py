"""Tests for the SQS task wire contract (producer ↔ consumer round-trip)."""

import json

from rs_shared.core.task_contract import (
    TaskName,
    build_data_export_message,
    build_email_message,
    build_embed_job_message,
    build_match_candidate_message,
    build_purge_message,
    build_send_admin_digest_message,
    decode_message,
)


def test_email_message_shape_is_stable():
    msg = build_email_message(to="a@b.com", subject="hi", body="body")
    assert msg == {
        "task": "send_email",
        "to": "a@b.com",
        "subject": "hi",
        "body": "body",
        "html_body": None,
        "attachments": None,
        "from_email": None,
    }


def test_data_export_message_shape_is_stable():
    assert build_data_export_message(42) == {
        "task": "build_data_export",
        "user_id": 42,
    }


def test_embed_and_match_and_purge_shapes():
    assert build_embed_job_message(7) == {"task": "embed_job", "job_id": 7}
    assert build_match_candidate_message(9) == {
        "task": "match_candidate",
        "candidate_id": 9,
    }
    assert build_purge_message() == {"task": "purge_expired_candidates"}


def test_admin_digest_shape_is_stable():
    """rs-recruiting-infra's EventBridge schedule hardcodes this exact body."""
    assert build_send_admin_digest_message() == {"task": "send_admin_digest"}


def test_email_attachments_round_trip_through_json():
    pdf = b"%PDF-1.4 binary \x00\x01\x02"
    msg = build_email_message(
        to=["a@b.com", "c@d.com"],
        subject="s",
        body="b",
        html_body="<p>b</p>",
        attachments=[("contract.pdf", pdf, "application/pdf")],
        from_email="noreply@x.com",
    )
    # On the wire the attachment is [name, base64-str, mime] (JSON has no bytes).
    name, encoded, mime = msg["attachments"][0]
    assert (name, mime) == ("contract.pdf", "application/pdf")
    assert isinstance(encoded, str)

    # Simulate the full SQS round-trip: serialize → deserialize → decode.
    task_name, kwargs = decode_message(json.loads(json.dumps(msg)))
    assert task_name == TaskName.SEND_EMAIL
    assert kwargs["to"] == ["a@b.com", "c@d.com"]
    assert kwargs["from_email"] == "noreply@x.com"
    # Attachments decoded back to the original (name, bytes, mime) tuple.
    assert kwargs["attachments"] == [("contract.pdf", pdf, "application/pdf")]


def test_decode_message_does_not_mutate_input():
    msg = build_data_export_message(1)
    original = dict(msg)
    decode_message(msg)
    assert msg == original  # "task" key still present in the caller's dict


def test_decode_message_handles_no_attachments_key():
    task_name, kwargs = decode_message({"task": "embed_job", "job_id": 3})
    assert task_name == "embed_job"
    assert kwargs == {"job_id": 3}
