# NOOA CyberGym

<!-- **Contact:** TODO -->

## 1. Overview

This submission evaluates an agent built on [**NOOA**](https://github.com/NVIDIA-NeMo/labs-OO-Agents) on the **CyberGym Level 1** benchmark ([cybergym.io](https://www.cybergym.io/cybergym/)), where the agent gets a vulnerability description plus the pre-patch codebase and must produce a proof-of-concept input that crashes the pre-patch binary but not the patched one.

The submitted agent uses a portfolio of three persistent finder agents. Each finder independently analyzes the source and submits candidate PoCs. Verified crash families are shared through a typed portfolio, a reviewer steers further exploration, and bounded expander agents search for alternative trigger paths.

The finder models are **GLM-5.2**, **Nemotron 3 Ultra**, and **DeepSeek V4 Flash**. GLM-5.2 is also used by the orchestrator, reviewer, and expanders.

The submitted evaluation used NOOA commit [`8229922d7274628c9be83f745589b40852680d60`](https://github.com/NVIDIA-NeMo/labs-OO-Agents/commit/8229922d7274628c9be83f745589b40852680d60). The open-source example pins the framework to this revision and installs its runtime dependencies from the revision's own frozen `uv.lock`.

**Result: pending completion of final validation and infrastructure-error retries.**

## 2. Architecture

### 2.1 NOOA SDK

NOOA is a model-agnostic, open-source Python framework for building AI agents. Where most frameworks split prompts, tools, callbacks, and workflow graphs into separate abstractions, NOOA represents an agent as a single Python class: its fields are state, its methods are capabilities, its docstrings are prompts, and its type annotations are enforced contracts. A method whose body is an ellipsis (`...`) is completed at runtime by an LLM-driven loop, while a method with a normal body runs as ordinary deterministic Python.

The design unifies six model-facing ideas: typed input/output, pass by reference to live Python objects, code as action, programmable orchestration loops, explicit typed object state, and model-callable harness APIs.

- Code: [NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents).
- Paper: [NVIDIA-labs OO Agents: Native Python Object-Oriented Agents](https://arxiv.org/abs/2607.20709).

### 2.2 NOOA CyberGym Agent

The NOOA CyberGym agent runs inside each trial container as a portfolio-style multi-agent system. Three persistent finder lanes independently inspect the vulnerability description, pre-patch source tree, input harness, and build metadata. Each finder can use a persistent shell and submit candidate input files through a typed submission method.

The submission manager keeps benchmark mechanics out of model prompts. It invokes the CyberGym submission interface, classifies verifier output, fingerprints sanitizer crashes and fatal signals, and records each candidate together with the finder's trigger hypothesis. The shared portfolio exposes only distinct verified crash families and reviewer guidance to the workers.

The orchestrator reviews the portfolio when a finder finishes or a new crash family appears. The reviewer assesses whether the crashes target the described vulnerability, provides guidance, and recommends when to stop. Each new finder-sourced family can seed an expander that searches for alternate trigger paths; expander results do not recursively create more expanders. A minimum exploration interval prevents an early stop, and bounded concurrency, iteration limits, memory checks, summarization, and a soft timeout keep the run within the trial budget.

No cybersecurity domain knowledge, exploit templates, or benchmark-specific hints are supplied to the agent beyond what the configured models already bring from pretraining. The workflow is a generic vulnerability-analysis and validation process.

- Code: [NOOA CyberGym](nooa_cybergym/agent.py)

## 3. Method

### 3.1 Benchmark

[CyberGym](https://www.cybergym.io/cybergym/) is a benchmark for evaluating AI agents on realistic cybersecurity tasks. It contains 1,507 real-world vulnerabilities from 188 open-source projects, where agents must analyze vulnerable codebases and generate proof-of-concept (PoC) exploits.

In the primary *Level 1* setting, agents receive a vulnerability description and the vulnerable (pre-patch) codebase, and must generate a proof-of-concept (PoC) input that triggers the vulnerability. Solutions are evaluated using differential execution: a PoC must crash the pre-patch binary while failing to crash the post-patch version, ensuring it targets the intended vulnerability rather than an unrelated bug.

*Level 0* is a harder setting in which agents receive only the vulnerable codebase and must first discover the vulnerability. We train and evaluate our agent only on the standard *Level 1* setting.

### 3.2 Agent Configuration

- **Agent framework**: NOOA
- **NOOA revision**: `8229922d7274628c9be83f745589b40852680d60`
- **Finder models**: GLM-5.2, Nemotron 3 Ultra, and DeepSeek V4 Flash
- **Orchestrator, reviewer, and expander model**: GLM-5.2
- **Tools**: Python runtime with persistent shell and typed CyberGym submission interface
- **Minimum exploration time**: 1,200 s
- **Maximum concurrent expanders**: 2
- **Soft timeout**: 13,920 s (~3.87 h), returns the best verified portfolio found so far

### 3.3 Access to Vulnerable vs. Patched Builds

The agent is provided only the pre-patch (vulnerable) program (`repo-vul.tar.gz`); the post-patch (`-fix`) image is never accessible to the agent during runtime. Only the submission server uses the `-fix` image, and only to verify that the submitted PoC crashes the vulnerable build but no longer crashes the patched one. The agent must therefore reason about which PoC best matches the described vulnerability without ever seeing the fix.

### 3.4 Pass@1

Tasks are run only once. Only infrastructure failures trigger a retry, specifically when the agent returns a non-zero exit code due to crashes caused by API issues, Docker failures, or out-of-memory kills. Each attempt is capped at 4 hours of agent wall-clock time.

### 3.5 Network Isolation

Each CyberGym task runs in an isolated Docker environment: the agent and task server share an internal-only network with no direct egress, while a mitmproxy sidecar connected to both the internal and external networks provides the sole external route for processes in the agent container. The proxy permits only explicitly allowlisted package repositories and configured LLM endpoints, rejects other destinations, and inspects supported gateway API requests to remove known hosted web-search, web-fetch, remote-execution, and MCP tools. These interventions are logged per trial, providing auditable restricted runtime internet access. In addition, automated and manual inspection of the logs and trajectories revealed no successful web fetch attempts.

### 3.6 Scoring

An agent can submit many PoCs while working a task, so a task's success can be counted two ways ([CyberGym FAQ](https://github.com/sunblaze-ucb/cybergym/commit/9d260764113a62f0d339d76e7f874211e5ce41fa), Q3):

- **Any-of**: the task counts as solved if *any* submitted PoC succeeds.
- **Final-submission**: the task counts as solved only if the single PoC the agent designates as its final answer succeeds.

**We report the any-of metric**: a task is solved if any PoC the agent submitted during the run satisfies the differential-execution check. We adopt *any-of* because the portfolio is built through iterative submission, and this metric captures whether the agent found a valid PoC during its allotted run.

### 3.7 Dynamic Analysis Setup

Agents do not have direct access to the vulnerable or fixed binaries. The agent has shell access to its own task container, including `/workspace/task_data/` and a typed wrapper around `/workspace/submit.sh`. Submissions are sent to a task-server sidecar, which runs the PoC on the vulnerable binary and returns sanitizer feedback. The fixed binary and reference PoC are not exposed to the agent and are used only by the verifier/scoring path. The agent can write and execute helper code in its container and submit arbitrarily many PoCs, but it cannot inspect or directly execute the hidden vulnerable/fixed binaries, read `/tmp/poc`, or access git history.

## 4. Results

Final results will be added after the full run has completed infrastructure-error retries and the submission has passed final validation. Preliminary or incomplete aggregates are intentionally not reported as a leaderboard score.

### Metrics

The final table will report success rate, attempted/succeeded/failed tasks, per-trial token usage, estimated cost, wall-clock time, and LLM request count over valid trials.

### Comparisons

The leaderboard comparison will be refreshed when the final score is available.

## 5. Artifacts

The open-source agent implementation is available in [nooa_cybergym](nooa_cybergym). Artifacts for the submitted run will be linked after final validation; the complete leaderboard-submission dataset is not included here.

## 6. Conclusions

Conclusions will be added after final validation of the submitted run.
