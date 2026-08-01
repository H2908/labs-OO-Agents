# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Tests for NeMo Relay middleware when nemo_relay is NOT installed.

These tests verify that install_nemo_relay() and nemo_relay_scope() raise ImportError
with helpful install instructions when nemo_relay is not available. They run
regardless of whether nemo_relay is installed by monkeypatching the flag.
"""

from unittest.mock import MagicMock

import pytest

import nooa.nemo_relay_middleware as nm


@pytest.fixture()
def _no_nemo_relay(monkeypatch):
    """Simulate nemo_relay not being installed."""
    monkeypatch.setattr(nm, "_HAS_NEMO_RELAY", False)


class TestImportErrorWhenMissing:
    """Verify ImportError is raised when nemo_relay is not available."""

    @pytest.mark.usefixtures("_no_nemo_relay")
    def test_install_nemo_relay_raises_import_error(self):
        """install_nemo_relay() raises ImportError when nemo_relay is not installed."""
        from nooa.runtime.event_manager import EventManager

        em = EventManager()
        with pytest.raises(ImportError, match="nemo_relay is required"):
            nm.install_nemo_relay(em)

    @pytest.mark.usefixtures("_no_nemo_relay")
    @pytest.mark.asyncio
    async def test_nemo_relay_scope_raises_import_error(self):
        """nemo_relay_scope() raises ImportError when nemo_relay is not installed."""
        agent = MagicMock()
        agent.event_manager = MagicMock()
        with pytest.raises(ImportError, match="nemo_relay is required"):
            async with nm.nemo_relay_scope(agent, "test-scope"):
                pass
