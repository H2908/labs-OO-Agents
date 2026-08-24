# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Error-rendering parity between the in-process and sandbox execution backends.

The sandbox backend marshals exceptions across a process boundary, so the live
``__traceback__`` cannot survive. These tests pin the requirement that the
agent-facing error text stays equivalent regardless of backend.
"""

from __future__ import annotations

import pytest

from nooa import Agent
from nooa.errors.formatting import format_error_for_llm
from nooa.runtime.sandbox.config import SandboxConfig
from nooa.runtime.sandbox.executor import SandboxedExecutor
from nooa.unifiedllm import FakeLLMClient

pytestmark = pytest.mark.sandbox

_SANDBOX = SandboxConfig(require=False, network=True, filesystem=False)

# Error on line 6 so an off-by-one in offset handling is visible.
_CODE = "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nboom = None.strip()\n"


def _agent() -> Agent:
    class _T(Agent, llm=FakeLLMClient()):
        pass

    return _T()


async def _render(*, sandboxed: bool) -> str:
    """Run _CODE on one backend and return the error text shown to the LLM."""
    agent = _agent()
    executor = None
    kwargs = {}
    if sandboxed:
        executor = SandboxedExecutor(agent, _SANDBOX, cell_timeout=15.0)
        kwargs["sandbox_executor"] = executor
    try:
        result = await agent.runtime.execute_code(
            _CODE, execution_count=1, wrap_in_function=True, **kwargs
        )
        assert result.error is not None, "expected the cell to raise"
        return format_error_for_llm(result.error, _CODE, line_offset=result.wrapper_line_offset)
    finally:
        if executor is not None:
            await executor.aclose()


async def test_inprocess_renders_frame_context() -> None:
    """Baseline: the in-process backend already reports location."""
    rendered = await _render(sandboxed=False)
    assert "Cell In[1], line 6" in rendered
    assert "None.strip()" in rendered
    assert "AttributeError" in rendered


async def test_sandbox_renders_frame_context() -> None:
    """The sandbox backend must report the same location, not a bare message."""
    rendered = await _render(sandboxed=True)
    assert "Cell In[1], line 6" in rendered
    assert "None.strip()" in rendered
    assert "AttributeError" in rendered


async def test_backends_render_identical_frame_lines() -> None:
    """Frame location and source text match across backends.

    Caret columns are deliberately out of scope: they are computed in wrapper
    coordinates and the two backends anchor them differently. Restoring frame
    context is separable from making carets column-accurate.
    """
    inproc = await _render(sandboxed=False)
    sandboxed = await _render(sandboxed=True)

    assert "Cell In[1], line 6" in inproc
    assert "Cell In[1], line 6" in sandboxed
    assert inproc.splitlines()[-1] == sandboxed.splitlines()[-1]
