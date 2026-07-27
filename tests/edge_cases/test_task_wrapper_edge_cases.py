# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Edge cases for TaskWrapper.

Focus on:
- `task.abort()` called from nested method
- `task.replan()` called from REPL during generation
- `task.current()` accessed from nested method

``task`` is the planned generation-session builtin (``task.abort`` /
``task.replan`` / ``task.current``), not ``self.todo`` / TodoManager.

These tests are skipped until TaskWrapper is implemented and injected into
PurePython / CodeAct execution builtins. ``GenerationAborted`` already exists
for ``task.abort()`` (see ``nooa.errors``).
"""

from __future__ import annotations

from typing import Any

import pytest

from nooa import Agent, strategy
from nooa.errors import GenerationAborted
from nooa.strategies.pure_python import PurePythonStrategy
from nooa.unifiedllm import FakeLLMClient, LLMResponse

pytestmark = pytest.mark.skip(reason="TaskWrapper (task.abort/replan/current) is not implemented yet")


def _resp(content: str) -> LLMResponse:
    """Create a test LLM response with the given content."""
    return LLMResponse(
        raw_response=None,
        content=content,
        tool_calls=[],
        finish_reason="stop",
        assistant_message={"role": "assistant", "content": content},
    )


_TEST_LLM = FakeLLMClient()


class TaskWrapperAgent(Agent, llm=_TEST_LLM):
    """Agent for TaskWrapper edge cases."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.seen: tuple[str, str, str | None] | None = None

    @strategy(PurePythonStrategy())
    async def outer(self) -> str:
        """Outer generation that may call nested helpers."""
        ...

    @strategy(PurePythonStrategy())
    async def inner(self) -> str:
        """Nested generation method."""
        ...

    @strategy(PurePythonStrategy())
    async def work(self) -> str:
        """Single-method generation used for replan tests."""
        ...


@pytest.mark.asyncio
async def test_abort_from_nested_generation_method():
    """``task.abort()`` inside a nested generation aborts the outer call."""
    fake = FakeLLMClient(
        scripted_responses=[
            _resp("r = await self.inner()\nreturn r"),
            _resp("task.abort('stop nested')\nreturn 'never'"),
        ]
    )
    agent = TaskWrapperAgent(llm=fake)

    with pytest.raises(GenerationAborted, match="stop nested"):
        await agent.outer()


@pytest.mark.asyncio
async def test_replan_from_repl_during_generation():
    """``task.replan()`` restarts the PurePython loop; the next turn can finish."""
    fake = FakeLLMClient(
        scripted_responses=[
            _resp("task.replan('try again')"),
            _resp("return 'ok'"),
        ]
    )
    agent = TaskWrapperAgent(llm=fake)

    assert await agent.work() == "ok"
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_current_from_nested_method_sees_nested_call():
    """``task.current()`` inside a nested generation reports the nested call."""
    fake = FakeLLMClient(
        scripted_responses=[
            _resp("r = await self.inner()\nreturn r"),
            _resp(
                "c = task.current()\n"
                "self.seen = (c.method_name, c.id, c.parent_id)\n"
                "return 'done'"
            ),
        ]
    )
    agent = TaskWrapperAgent(llm=fake)

    assert await agent.outer() == "done"
    assert agent.seen is not None
    name, call_id, parent_id = agent.seen
    assert name == "inner"
    assert call_id  # non-empty id
    assert parent_id is not None  # links to outer CurrentCall
