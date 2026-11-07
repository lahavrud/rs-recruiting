"""Worker dispatch: unknown tasks must never be acked (#1078)."""

import json

import pytest

from rs_shared.core.task_contract import TaskName
from rs_shared.core.tasks import TASK_REGISTRY
from rs_worker import worker


async def test_unknown_task_raises_so_message_is_not_deleted():
    body = json.dumps({"task": "task_this_worker_has_never_heard_of"})

    with pytest.raises(worker.UnknownTaskError) as exc_info:
        await worker._process_message(body)

    assert str(exc_info.value) == "task_this_worker_has_never_heard_of"


async def test_known_task_runs_and_returns_its_name(monkeypatch):
    calls: list[dict] = []

    async def fake_sweep(**kwargs):
        calls.append(kwargs)

    monkeypatch.setitem(TASK_REGISTRY, TaskName.SWEEP_EMAIL_OUTBOX, fake_sweep)

    body = json.dumps({"task": TaskName.SWEEP_EMAIL_OUTBOX})
    assert await worker._process_message(body) == TaskName.SWEEP_EMAIL_OUTBOX
    assert calls == [{}]
