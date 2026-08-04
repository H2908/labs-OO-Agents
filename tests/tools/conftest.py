# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
"""Session-start check for shell-tool test prerequisites.

`test_shell_tools_modern.py` skipif-drops 145 tests when `rg` or `grep` is
missing from `PATH`. A skip is indistinguishable from a pass in the pytest
summary, so a base image that stops shipping ripgrep would silently erase
that coverage. Fail loud in CI; warn locally.
"""

from __future__ import annotations

import os
import shutil
import warnings

import pytest


def pytest_sessionstart(session: pytest.Session) -> None:
    missing = [tool for tool in ("rg", "grep") if shutil.which(tool) is None]
    if not missing:
        return
    msg = (
        f"tests/tools/ prerequisite missing on PATH: {', '.join(missing)}. "
        "Install ripgrep (`apt install ripgrep` / `brew install ripgrep`); "
        "see tests/README.md."
    )
    # CI must fail loud rather than silently skip 145 tests. Locally, warn
    # but do not block — a contributor running `pytest tests/agents/` should
    # not be forced to install a dep for a suite they are not touching.
    if os.environ.get("CI"):
        pytest.exit(msg, returncode=1)
    warnings.warn(msg, UserWarning, stacklevel=1)
