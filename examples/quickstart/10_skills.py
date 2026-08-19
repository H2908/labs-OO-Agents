# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# ruff: noqa: F403,F405
"""Quickstart 10: Skills — inject curated context into an agent.

uv run python examples/quickstart/10_skills.py
"""

from pathlib import Path

from nooa import TextSkill
from nooa.skill_registry import SkillRegistry
from nooa.util.quickstart import *

ASSETS = Path(__file__).parent.parent / "assets"


class DesignProposal(BaseModel):
    aesthetic_direction: str = Field(
        description="A specific visual direction in one short sentence.",
    )
    memorable_detail: str = Field(
        description="The one detail visitors should remember, in one short sentence.",
    )
    anti_patterns_to_avoid: list[str] = Field(
        min_length=2,
        max_length=2,
        description="Exactly two visual anti-patterns rejected by the skill guidance.",
    )


class FrontendAgent(Agent, llm=llm):
    """Agent with a single file-based skill."""

    frontend_design: TextSkill

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.frontend_design = TextSkill(path=ASSETS / "frontend-design")

    @strategy(PredictStrategy())
    async def respond(self, prompt: str) -> DesignProposal:
        """Respond using this attached skill guidance:

        {doc(self.frontend_design)}

        Return ``DesignProposal`` directly; do not wrap it in another object.
        """
        ...


class GenericAgent(Agent, llm=llm):
    """Agent that registers and activates a model-facing skill."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.skills = SkillRegistry(self)
        self.skills.register(
            "local.frontend_design",
            TextSkill(path=ASSETS / "frontend-design"),
        )
        self.skills.activate(["local.frontend_design"])

    @strategy(PredictStrategy())
    async def respond(self, prompt: str) -> DesignProposal:
        """Respond using this active skill guidance:

        {doc(self.frontend_design)}

        Return ``DesignProposal`` directly; do not wrap it in another object.
        """
        ...


@autorun
async def main():
    request = (
        "Follow the attached frontend-design skill to propose a memorable aesthetic "
        "direction for a responsive landing page. Include one signature detail and "
        "exactly two visual anti-patterns that the skill explicitly rejects. Keep each "
        "field and anti-pattern to one short sentence."
    )

    print("=== Direct TextSkill attachment ===")
    agent = FrontendAgent()
    result = await agent.respond(request)
    print(result)

    print("\n=== SkillRegistry activation ===")
    agent = GenericAgent()
    result = await agent.respond(request)
    print(result)
