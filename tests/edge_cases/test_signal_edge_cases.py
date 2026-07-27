# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Edge cases for signals.

Focus on:
- Signal queued during generation session
- Signal that calls @strategy method needing generation
- Multiple signals queued during long generation

"Signals" here are implemented (non-ellipsis) agent methods invoked concurrently
while a generation method holds the actor's generation lock / session. They are
scheduled as asyncio tasks — there is no separate SignalQueue API.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from nooa import Agent, strategy
from nooa.strategies.pure_python import PurePythonStrategy
from nooa.unifiedllm import FakeLLMClient, LLMResponse


def _resp(content: str) -> LLMResponse:
    """Create a test LLM response with the given content."""
    return LLMResponse(
        raw_response=None,
        content=content,
        tool_calls=[],
        finish_reason="stop",
        assistant_message={"role": "assistant", "content": content},
    )


class GatedFakeLLM(FakeLLMClient):
    """FakeLLM that blocks inside acall until ``gate`` is set.

    Lets tests schedule concurrent "signal" work while a generation session
    is still open (stock FakeLLMClient returns instantly).
    """

    def __init__(
        self,
        scripted_responses: list[LLMResponse] | None = None,
        *,
        gate: asyncio.Event | None = None,
    ):
        super().__init__(scripted_responses=scripted_responses)
        self.entered = asyncio.Event()
        self.gate = gate if gate is not None else asyncio.Event()
        if gate is None:
            self.gate.set()

    async def acall(
        self,
        messages: list[dict[str, Any]],
        tools: list | None = None,
        output_model: type | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        self.entered.set()
        await self.gate.wait()
        return await super().acall(messages, tools=tools, output_model=output_model, **kwargs)


_TEST_LLM = FakeLLMClient()


class SignalAgent(Agent, llm=_TEST_LLM):
    """Agent for signal-during-generation edge cases."""

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self.logged_events: list[str] = []
        self.order: list[str] = []

    @strategy(PurePythonStrategy())
    async def long_gen(self) -> str:
        """Long generation session held open by a gated LLM."""
        ...

    @strategy(PurePythonStrategy())
    async def nested_gen(self) -> str:
        """Generation method invoked from a concurrent signal."""
        ...

    async def log_signal(self, msg: str) -> None:
        """Implemented method — runs without the generation lock."""
        self.logged_events.append(f"signal-{msg}")
        self.order.append(f"signal-{msg}")

    async def signal_calls_gen(self) -> str:
        """Implemented method that awaits a generation method (needs the lock)."""
        self.order.append("signal-enter")
        result = await self.nested_gen()
        self.order.append("signal-exit")
        return result


@pytest.mark.asyncio
async def test_signal_queued_during_generation_session():
    """Implemented signal runs while a generation session is still open."""
    gate = asyncio.Event()
    fake = GatedFakeLLM(scripted_responses=[_resp("return 'done'")], gate=gate)
    agent = SignalAgent(llm=fake)

    gen_task = asyncio.create_task(agent.long_gen())
    await fake.entered.wait()

    sig_task = asyncio.create_task(agent.log_signal("mid"))
    await asyncio.wait_for(sig_task, timeout=1.0)

    # Signal completed while generation was still held open.
    assert agent.logged_events == ["signal-mid"]
    assert not gen_task.done()

    gate.set()
    assert await gen_task == "done"
    assert fake.call_count == 1


@pytest.mark.asyncio
async def test_signal_that_calls_strategy_method_needing_generation():
    """Signal awaiting a @strategy method waits for the outer generation lock."""
    gate = asyncio.Event()
    fake = GatedFakeLLM(
        scripted_responses=[
            _resp("return 'outer'"),
            _resp("return 'from-sig'"),
        ],
        gate=gate,
    )
    agent = SignalAgent(llm=fake)

    gen_task = asyncio.create_task(agent.long_gen())
    await fake.entered.wait()

    sig_task = asyncio.create_task(agent.signal_calls_gen())
    # Give the signal time to enter and block on the generation lock.
    await asyncio.sleep(0.05)
    assert agent.order == ["signal-enter"]
    assert not sig_task.done()

    gate.set()
    assert await gen_task == "outer"
    assert await sig_task == "from-sig"
    assert fake.call_count == 2
    assert agent.order == ["signal-enter", "signal-exit"]


@pytest.mark.asyncio
async def test_multiple_signals_queued_during_long_generation():
    """Several implemented signals all complete during one open generation."""
    gate = asyncio.Event()
    fake = GatedFakeLLM(scripted_responses=[_resp("return 'done'")], gate=gate)
    agent = SignalAgent(llm=fake)

    gen_task = asyncio.create_task(agent.long_gen())
    await fake.entered.wait()

    signal_tasks = [asyncio.create_task(agent.log_signal(str(i))) for i in range(5)]
    await asyncio.wait_for(asyncio.gather(*signal_tasks), timeout=1.0)

    assert agent.logged_events == [f"signal-{i}" for i in range(5)]
    assert not gen_task.done()

    gate.set()
    assert await gen_task == "done"
    assert fake.call_count == 1


@pytest.mark.asyncio
async def test_mixed_signals_during_generation_lock_and_no_lock():
    """Non-gen signals finish mid-session; gen-needing signals wait for unlock."""
    gate = asyncio.Event()
    fake = GatedFakeLLM(
        scripted_responses=[
            _resp("return 'outer'"),
            _resp("return 'from-sig'"),
        ],
        gate=gate,
    )
    agent = SignalAgent(llm=fake)

    gen_task = asyncio.create_task(agent.long_gen())
    await fake.entered.wait()

    free_sig = asyncio.create_task(agent.log_signal("free"))
    blocked_sig = asyncio.create_task(agent.signal_calls_gen())
    await asyncio.wait_for(free_sig, timeout=1.0)
    await asyncio.sleep(0.05)

    assert agent.logged_events == ["signal-free"]
    assert agent.order == ["signal-free", "signal-enter"]
    assert not blocked_sig.done()

    gate.set()
    assert await gen_task == "outer"
    assert await blocked_sig == "from-sig"
    assert agent.order == ["signal-free", "signal-enter", "signal-exit"]
