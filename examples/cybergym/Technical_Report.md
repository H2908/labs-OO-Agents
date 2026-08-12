# NOOA CyberGym

## 1. Overview

This example implements a [NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents)-based agent for [CyberGym](https://www.cybergym.io/cybergym/) Level 1. The agent receives a vulnerability description and the pre-patch source tree, then generates raw-input proof-of-concept files for the CyberGym verifier.

The agent uses a portfolio-style multi-agent architecture:

- Three persistent finder agents independently inspect source and generate PoCs.
- A deterministic submission manager classifies verifier output and fingerprints crashes.
- A shared portfolio communicates verified crash families and reviewer guidance.
- A reviewer steers exploration and decides when sufficient diversity has been reached.
- Expander agents derive alternate trigger paths from newly discovered crash families.

The configured finder models are GLM-5.2, Nemotron 3 Ultra, and DeepSeek V4 Flash. GLM-5.2 is also used by the orchestrator, reviewer, and expanders.

## 2. NOOA agent model

NOOA represents an agent as a Python object: fields are state, methods are capabilities, docstrings are prompts, and return annotations are contracts. A method with an ellipsis body is executed by an LLM strategy, while methods with ordinary Python bodies remain deterministic.

The CyberGym implementation separates model-driven exploration from benchmark mechanics:

- [agent.py](nooa_cybergym/agent.py) defines the finder, expander, portfolio, reviewer, and orchestration loop.
- [submissions.py](nooa_cybergym/submissions.py) owns verifier invocation, result classification, crash fingerprinting, and submission records.
- [shell_tools.py](nooa_cybergym/shell_tools.py) provides persistent shell and file operations.
- [util.py](nooa_cybergym/util.py) creates model clients and configures summarization and tracing.
- [main.py](nooa_cybergym/main.py) is the in-container entry point.
- [run.py](nooa_cybergym/run.py) is the host-side CyberGym and Docker integration.

## 3. Architecture

### 3.1 Finder lanes

Each configured lane owns a persistent `Finder` instance. A finder reads the vulnerability description, source tree, input harness, and build metadata. It creates minimal candidate inputs and calls its typed `submit()` method with both the file path and a concise trigger hypothesis.

Finders do not execute the hidden vulnerable binary directly. The submission API is their test loop. Its result includes a status, exit code, output excerpt, submission number, and normalized crash fingerprint.

The lanes are:

| Lane | Model alias |
|---|---|
| GLM-5.2 | `glm-5.2` |
| Nemotron 3 Ultra | `nvidia/nemotron-3-ultra` |
| DeepSeek V4 Flash | `deepseek-v4-flash` |

Aliases and gateway model identifiers are defined in [llm_config.yaml](nooa_cybergym/llm_config.yaml).

### 3.2 Submission manager

`SubmissionManager` is the sole interface to `/workspace/submit.sh`. It:

1. Shell-quotes the candidate path and invokes the verifier.
2. Parses the final JSON object from the verifier output.
3. Classifies the result as `crashed`, `crashed_suspect`, `no_crash`, `timeout`, or `server_error`.
4. Recognizes sanitizer signatures, fatal process signals, infrastructure failures, and assertion-only failures.
5. Creates a stable crash fingerprint from sanitizer type, error type, deduplication token, stack frames, assertions, and exit behavior.
6. Records submission metadata and worker hypotheses in `submissions.jsonl`.

Crash fingerprints allow the orchestration layer to reason about distinct families without placing raw submission bookkeeping in the model prompts.

### 3.3 Shared portfolio

The `Portfolio` is the only shared state between workers. It stores submissions, reviewer guidance, stop state, and bookkeeping for expanded crash families.

Finders receive portfolio changes as append-only `Feedback` events. The rendered portfolio contains only distinct verified crash families, their representative PoC paths, relevant stack frames, worker hypotheses, and current reviewer guidance. Stable rendering helps preserve prompt-cache reuse between meaningful changes.

### 3.4 Reviewer

The orchestrator reviews the portfolio whenever a finder finishes or a new crash family appears. The reviewer returns a typed `Review` containing:

- `on_target`: whether the discovered crashes match the described vulnerability.
- `guidance`: what workers should explore next.
- `stop`: whether further exploration is unlikely to find another family.
- `reasoning`: a concise justification.

A stop recommendation is honored only after the minimum exploration interval, which defaults to 1,200 seconds.

### 3.5 Expanders

Each distinct finder-sourced crash family can seed one `Expander`. Expanders read the submitted seed, inspect the implicated source path, trace callers and branch conditions backward, and create minimal mutations intended to reach the same vulnerability through different paths.

At most two expanders run concurrently by default. Expander-generated crashes do not recursively seed more expanders.

### 3.6 Lifecycle and resource bounds

Finders are persistent objects and are started again after a CodeAct call finishes, retaining their event histories and portfolio feedback. The orchestrator also applies:

- A 3,500 MB process RSS guard to exit before the container limit.
- A default 13,920-second cooperative soft timeout.
- A default 300 CodeAct iterations per finder call.
- Half that iteration budget for each expander call.
- Token-budget summarization at 80% of each model's configured context window.

At shutdown, active workers are cancelled and the current portfolio is written as the final result.

## 4. CyberGym environment

### 4.1 Task data

The runner generates a CyberGym task directory and mounts it at `/workspace/task_data`. The agent reads `description.txt` and extracts `repo-vul.tar.gz` once before launching workers. `/workspace/submit.sh` is mounted read-only and is the only route to vulnerable-build execution.

### 4.2 Vulnerable and fixed builds

The agent receives the pre-patch source but cannot inspect or directly execute the hidden vulnerable or fixed binaries. Submissions are sent to the CyberGym server, which executes candidates against the vulnerable build and returns the result. Fixed-build validation remains outside the agent container and is performed by the validation workflow.

### 4.3 Network boundary

The public runner supports CyberGym's firewall mode. The agent container joins the firewall network, uses proxy environment variables supplied by CyberGym, and adds the hostname of the configured LLM gateway to the proxy allowlist. Other endpoints can be supplied explicitly through `CYBERGYM_FIREWALL_EXTRA_DOMAINS`.

The model endpoint is selected from `OPENAI_BASE_URL`, then `OPENAI_API_BASE`, with the configured NVIDIA inference endpoint as the default. Credentials are supplied at runtime and are not stored in the repository.

## 5. Reproducibility

The image is built from the repository root and installs NOOA from the same checkout as the example. Runtime dependencies are exported from `uv.lock` and installed with hash verification. This keeps the framework, agent, and dependency graph aligned for a run.

The standard workflow is documented in [README.md](README.md):

1. Run `scripts/setup.sh` to create the uv environment, install CyberGym, fetch the 10-task subset, and build the agent image.
2. Run `scripts/start_server.sh` in a dedicated terminal.
3. Run `scripts/run_subset.sh` to execute the configured tasks.
4. Run `scripts/validate.sh` to replay submissions against the fixed builds.

Each task records its invocation, console output, final portfolio, submission log, portable journal traces, and ATIF trajectory under its run directory.

## 6. Verification

The checked-in test suite covers the current implementation's deterministic behavior, including:

- Sanitizer, signal, timeout, infrastructure, and assertion classification.
- Stable crash fingerprint and cluster generation.
- Submission path quoting and hypothesis recording.
- Portfolio rendering and append-only finder feedback.
- Crash-family deduplication and expander selection.
- Finder, expander, and orchestrator configuration.
- Model alias and reasoning-effort resolution.
- Journal and ATIF trace installation.
- Soft-timeout output and tracing-shutdown behavior.

Run the focused suite from the repository root:

```bash
uv run pytest -q \
  tests/test_cybergym_portfolio_agent.py \
  tests/test_cybergym_portfolio_main.py
```

The Docker image is additionally exercised with in-container import, CLI, artifact-path, and three-model registry smoke tests. End-to-end benchmark results depend on access to an OpenAI-compatible gateway exposing all configured model identifiers.

## 7. Output artifacts

A run produces:

```text
<run-root>/logs/<task>-<agent-id>/
├── args.json
├── console.log
├── agent/
│   └── trajectory.json
└── artifacts/
    ├── output.txt
    ├── submissions.jsonl
    └── traces/
```

`output.txt` contains the final portfolio summary. `submissions.jsonl` records every candidate and normalized fingerprint. `trajectory.json` uses the ATIF schema, while `traces/` contains portable NOOA journal records for detailed inspection.
