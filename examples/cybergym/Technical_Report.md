# NOOA CyberGym

<!-- **Contact:** TODO -->

## 1. Overview

This submission evaluates an agent built on [**NVIDIA-labs Object-Oriented Agents (NOOA)**](https://github.com/NVIDIA-NeMo/labs-OO-Agents) on the **CyberGym Level 1** benchmark ([cybergym.io](https://www.cybergym.io/cybergym/)), where the agent gets a vulnerability description plus the pre-patch codebase and must produce a proof-of-concept input that crashes the pre-patch binary but not the patched one.

Our CyberGym agent runs as a CodeAct agent with a shell and a todo manager, surveying the mounted source to locate the vulnerable function and author a minimal PoC. No cybersecurity domain knowledge or benchmark-specific hints are supplied beyond what the base model already brings from pretraining.

The underlying model is **OpenAI GPT-5.5** with reasoning effort set to `xhigh`.

**Result: 1,308 / 1,507 tasks solved = 86.8% pass@1.**

## 2. Architecture

### 2.1 NOOA SDK

NVIDIA-labs Object-Oriented Agents (NOOA) is a model-agnostic, open-source Python framework for building AI agents. Where most frameworks split prompts, tools, callbacks, and workflow graphs into separate abstractions, NOOA represents an agent as a single Python class: its fields are state, its methods are capabilities, its docstrings are prompts, and its type annotations are enforced contracts. A method whose body is an ellipsis (`...`) is completed at runtime by an LLM-driven loop, while a method with a normal body runs as ordinary deterministic Python.

The design unifies six model-facing ideas: typed input/output, pass by reference to live Python objects, code as action, programmable orchestration loops, explicit typed object state, and model-callable harness APIs.

* Code: [NVIDIA-labs Object-Oriented Agents (NOOA)](https://github.com/NVIDIA-NeMo/labs-OO-Agents).
* Paper: [NVIDIA-labs OO Agents: Native Python Object-Oriented Agents](https://arxiv.org/abs/2607.20709).

### 2.2 NOOA CyberGym Agent

The NOOA CyberGym agent runs inside each trial container as a CodeAct agent that has full access to a Python runtime and is equipped with two additional tools: a shell (file search, source inspection, and command execution over the mounted codebase) and a todo manager for tracking multi-step work. On each task it reads the vulnerability description, surveys the mounted pre-patch source and build setup, identifies the vulnerable function and the input shape that reaches it, and authors a minimal, deterministic proof-of-concept, which it submits through the CyberGym submission interface.

A deterministic scoring layer wraps the agent and keeps the scoring logic out of the agent's context. A submission method sends the authored PoC, replays it against the sanitizer-instrumented vulnerable binary, and returns a typed outcome (crash, ambiguous crash, no crash, or timeout) rather than raw tool output. Before a submission is accepted, a lightweight single-turn judge confirms that the model's summary still targets the specific vulnerability class described in the task. On a mismatch, structured feedback is returned to the agent and it retries. Accepted PoCs are re-submitted three times and are only kept if they crash in at least two of the three replays, rejecting non-deterministic crashes that would not survive server-side differential verification. A soft timeout well inside the harness limit returns the best crashing PoC found so far if the loop has not already converged.

No cybersecurity domain knowledge, exploit templates, or benchmark-specific hints are supplied to the agent beyond what the base model already brings from pretraining; the workflow above is generic vulnerability validation. Performance is therefore attributable to the agent architecture and the underlying model rather than to task-specific steering.

* Code: [NOOA CyberGym](nooa_cybergym/main.py)

## 3. Methodology

### 3.1 Benchmark

[CyberGym](https://www.cybergym.io/cybergym/) is a benchmark for evaluating AI agents on realistic cybersecurity tasks. It contains 1,507 real-world vulnerabilities from 188 open-source projects, where agents must analyze vulnerable codebases and generate proof-of-concept (PoC) exploits.

In the primary *Level 1* setting, agents receive a vulnerability description and the vulnerable (pre-patch) codebase, and must generate a proof-of-concept (PoC) input that triggers the vulnerability. Solutions are evaluated using differential execution: a PoC must crash the pre-patch binary while failing to crash the post-patch version, ensuring it targets the intended vulnerability rather than an unrelated bug.

*Level 0* is a harder setting in which agents receive only the vulnerable codebase and must first discover the vulnerability. We train and evaluate our agent only on the standard *Level 1* setting.

### 3.2 Agent Configuration

* **Agent framework**: NVIDIA-labs Object-Oriented Agents (NOOA)
* **Model**: OpenAI GPT-5.5
* **Reasoning effort**: `xhigh`
* **Tools**: Python runtime with shell + todo manager
* **Soft timeout**: 13,920 s (~3.87 h), returns best crashing PoC found so far

### 3.3 Access to Vulnerable vs. Patched Builds

The agent is provided only the pre-patch (vulnerable) program (`repo-vul.tar.gz`); the post-patch (`-fix`) image is never accessible to the agent during runtime. Only the submission server uses the `-fix` image, and only to verify that the submitted PoC crashes the vulnerable build but no longer crashes the patched build. The agent must therefore reason about which PoC best matches the described vulnerability without ever seeing the fix.

### 3.4 Pass@1

Tasks were run only once. Only infrastructure failures triggered a retry, specifically when the agent returned a non-zero exit code due to crashes caused by API issues, Docker failures, or out-of-memory kills. Each attempt was capped at 4 hours of agent wall-clock time.

### 3.5 Network Isolation

Each CyberGym task runs in an isolated Docker environment: the agent and task server share an internal-only network with no direct egress, while a mitmproxy sidecar connected to both the internal and external networks provides the sole external route for processes in the agent container. The proxy permits only explicitly allowlisted package repositories and configured LLM endpoints, rejects other destinations, and inspects supported gateway API requests to remove known hosted web-search, web-fetch, remote-execution, and MCP tools. These interventions are logged per trial, providing auditable restricted runtime internet access. In addition, automated and manual inspection of the logs and trajectories revealed no successful web fetch attempts.

### 3.6 Scoring

An agent can submit many PoCs while working a task, so a task's success can be counted two ways ([CyberGym FAQ](https://github.com/sunblaze-ucb/cybergym/commit/9d260764113a62f0d339d76e7f874211e5ce41fa), Q3):

* **Any-of**: the task counts as solved if *any* submitted PoC succeeds.
* **Final-submission**: the task counts as solved only if the single PoC the agent designates as its final answer succeeds.

**We report the any-of metric**: a task is solved if any PoC the agent submitted during the run satisfies the differential-execution check. We adopt *any-of* because our agent's loop is built around iterative submission. It authors, submits, and refines candidate PoCs against the sanitizer-instrumented binary, keeping a crashing PoC as soon as one reproduces reliably, and *any-of* scores exactly that behavior without penalizing exploration.

### 3.7 Dynamic Analysis Setup

Agents did not have direct access to the vulnerable or fixed binaries. The agent had shell access to its own task container, including `/workspace/task_data/` and a `submit()` wrapper around `/workspace/submit.sh`. Submissions were sent to a task-server sidecar, which ran the PoC on the vulnerable binary and returned sanitizer feedback. The fixed binary and reference PoC were not exposed to the agent and were used only by the verifier/scoring path. The agent could write and execute helper code in its container and submit arbitrarily many PoCs, but it could not inspect or directly execute the hidden vulnerable/fixed binaries, read `/tmp/poc`, or access git history.

## 4. Results

### Metrics

The token, cost, and timing figures below are per-trial averages over the valid trials.

| Metric                 | Value     | Comment                                                                                                                   |
|------------------------|-----------|---------------------------------------------------------------------------------------------------------------------------|
| Success rate           | 86.8%     | The fraction of attempted tasks that succeeded.                                                                           |
| Tasks attempted        | 1,507     | The total number of CyberGym Level 1 tasks attempted.                                                                     |
| Tasks succeeded        | 1,308     | The number of tasks for which a submitted PoC passed the differential-execution check.                                    |
| Tasks failed           | 199       | The number of tasks for which no submitted PoC succeeded.                                                                 |
| Input tokens           | 343,277   | The average number of non-cached input tokens per trial, covering the prompt and context that were not served from cache. |
| Cache read tokens      | 3,629,915 | The average number of cached tokens read per trial.                                                                       |
| Output tokens          | 70,579    | The average number of output tokens generated per trial.                                                                  |
| Estimated cost (USD)   | $5.35     | The average cost per trial, computed as (input − cached) × $5/M + cached × $0.50/M + output × $30/M.                      |
| Wall-clock time (min)  | 36        | The average wall-clock time per trial, spanning environment build, agent execution, and verification.                     |
| LLM requests           | 44.4      | The average number of model API calls per trial, summed across the main agent and its subagent steps.                     |

### Comparisons

Top 9 published results on the CyberGym Level 1 leaderboard (one trial, sorted by success rate, as reported on [cybergym.io](https://www.cybergym.io/cybergym/), retrieved 2026-07-28).

| #  | Submission                 | Model(s)                                    | Score     | Date           | Source                                                                                                                                                                        |
|----|----------------------------|---------------------------------------------|-----------|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | Wiz Atlas                  | GPT-5.5, Claude Opus 4.6                    | 90.9%     | 2026-07-27     | [Wiz](https://www.wiz.io/blog/atlas-ai-vulnerability-researcher)                                                                                                              |
| 2  | Crystalline                | Claude Opus 4.6                             | 89.6%     | 2026-06-08     | [Independent researcher](https://github.com/synchopate/cybergym-logos)                                                                                                        |
| 3  | MDASH                      | GPT-5.4, Claude Opus 4.6, Claude Sonnet 4.6 | 88.4%     | 2026-05-12     | [Microsoft](https://www.microsoft.com/en-us/security/blog/2026/05/12/defense-at-ai-speed-microsofts-new-multi-model-agentic-security-system-tops-leading-industry-benchmark/) |
| 4  | **NOOA CyberGym**          | **GPT-5.5**                                 | **86.8%** | **2026-07-28** | **This work**                                                                                                                                                                 |
| 5  | Sangfor AI                 | GLM-5.2                                     | 86.3%     | 2026-07-21     | [Sangfor AI](https://github.com/Sangfor-AI/cybergym-submission-sangfor-ai)                                                                                                    |
| 6  | GPT-5.5-Cyber              | GPT-5.5-Cyber (OpenAI Agent)                | 85.6%     | 2026-06-22     | [OpenAI](https://openai.com/index/daybreak-securing-the-world/)                                                                                                               |
| 7  | Xuanwu Atuin AI            | GLM-5.2                                     | 84.8%     | 2026-07-22     | [Tencent Xuanwu Lab](https://xlab.tencent.com/en/2026/07/17/xuanwu-atuin-cybergym-glm52/)                                                                                     |
| 8  | Claude Mythos Preview      | Claude Mythos Preview (Anthropic Agent)     | 83.1%     | 2026-04-07     | [Anthropic](https://www.anthropic.com/claude-mythos-preview-system-card)                                                                                                      |
| 9  | GPT-5.5                    | GPT-5.5 (OpenAI Agent)                      | 81.8%     | 2026-04-23     | [OpenAI](https://openai.com/index/introducing-gpt-5-5)                                                                                                                        |
| 10 | GPT-5.4                    | GPT-5.4 (OpenAI Agent)                      | 79.0%     | 2026-04-23     | [OpenAI](https://openai.com/index/introducing-gpt-5-5)                                                                                                                        |

## 5. Artifacts

| Item                            | Link                                                  |
|---------------------------------|-------------------------------------------------------|
| NOOA CyberGym agent code        | [Link](nooa_cybergym/main.py)                        |
| ATIF trajectories               | [Link](task_artifacts) (`trajectory.json` files) |
| Logs                            | [Link](task_artifacts) (`output.txt` files)        |
| PoC submissions                 | [Link](task_artifacts) (`submissions` directory)   |
| Verifier results                | [Link](task_artifacts) (`result.txt` files)        |

The benchmark submission reported here was produced with an earlier, internal version of NOOA, predating the public open-source release of the framework. The code we share alongside this write-up is a cleaned-up version of that CyberGym agent, rebased on the publicly released NOOA. Minor differences in behavior and results between the two versions are therefore possible.

The PoC submissions and accompanying artifacts (trajectories, logs, results) shared here come from a separate run over 10 tasks, not from the run submitted to the leaderboard. This run used the exact same agent code. We re-ran these tasks manually because the original PoC submissions were discarded.

## 6. Conclusions

On CyberGym Level 1, the NOOA CyberGym agent solves 1,308 of 1,507 tasks (86.8% pass@1), placing it among the top published results on the leaderboard and ahead of every other fully open-source submission. It reaches this level with no cybersecurity domain knowledge, exploit templates, or benchmark-specific hints, only a generic vulnerability-validation workflow expressed as a single object-oriented NOOA agent. The result is therefore attributable to the agent architecture and underlying model rather than task-specific engineering, and it shows that a compact, fully open-source agent can compete with proprietary systems on realistic security tasks.
