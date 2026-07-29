# NOOA CyberGym Agent

[NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents)-based CyberGym agent for the [CyberGym](https://github.com/sunblaze-ucb/cybergym) benchmark.

- Read the [technical report](Technical_Report.md) for more details on the functionaltiy of the agent and how we evaluated it.
- This README documents one minimal path: run CyberGym's official 10-task subset with the CyberGym firewall/proxy. It does **not** require downloading the full ~240GB CyberGym dataset.

## Requirements

- Linux host with Docker
- Python 3.12 or 3.13
- Git LFS (`git lfs version` should work)
- LLM credentials available in `.env` or the shell environment

Typical `.env`:

```bash
OPENAI_API_KEY=...
OPENAI_API_BASE=https://api.openai.com/v1
```

If you want to change the model used update `nooa_cybergym/llm_config.yaml`.

## What gets downloaded

CyberGym uses two separate data sources:

1. **Task data** from the Hugging Face `cybergym` dataset: descriptions and vulnerable repo tarballs used by `cybergym.task.gen_task`.
2. **Server execution images** from Docker Hub: vulnerable/fixed images used by the CyberGym submission server.

For the 10-task subset below, this README fetches only the matching task-data paths with Git LFS and pulls only the matching Docker images. The server runs in CyberGym's Docker-image mode, so do **not** pass `--binary_dir`.

Official CyberGym subset used here:

```text
arvo:47101
arvo:3938
arvo:24993
arvo:1065
arvo:10400
arvo:368
oss-fuzz:42535201
oss-fuzz:42535468
oss-fuzz:370689421
oss-fuzz:385167047
```

## 1. Install CyberGym and fetch the subset

Run from this repository root:

```bash
export AGENT_REPO=$PWD
export CYBERGYM_REPO=$(realpath "$AGENT_REPO/cybergym_repo")

python3 -m venv "$AGENT_REPO/.venv"
source "$AGENT_REPO/.venv/bin/activate"
python3 -m pip install --upgrade pip

if [ ! -d "$CYBERGYM_REPO/.git" ]; then
  git clone https://github.com/sunblaze-ucb/cybergym.git "$CYBERGYM_REPO"
fi

cd "$CYBERGYM_REPO"
python3 -m pip install -e '.[dev,server]'

git lfs install
if [ ! -d "$CYBERGYM_REPO/cybergym_data/.git" ]; then
  GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/datasets/sunblaze-ucb/cybergym "$CYBERGYM_REPO/cybergym_data"
fi

SUBSET_LFS_INCLUDE='data/arvo/47101/**,data/arvo/3938/**,data/arvo/24993/**,data/arvo/1065/**,data/arvo/10400/**,data/arvo/368/**,data/oss-fuzz/42535201/**,data/oss-fuzz/42535468/**,data/oss-fuzz/370689421/**,data/oss-fuzz/385167047/**'
git -C "$CYBERGYM_REPO/cybergym_data" lfs pull --include="$SUBSET_LFS_INCLUDE"

python3 scripts/server_data/download_subset.py

ls -ld "$CYBERGYM_REPO/cybergym_data/data/arvo/10400"
docker image inspect n132/arvo:10400-vul >/dev/null
cd "$AGENT_REPO"
```

Keep using this virtual environment for host-side commands:

```bash
source "$AGENT_REPO/.venv/bin/activate"
```

## 2. Install this runner and build the agent image

```bash
source "$AGENT_REPO/.venv/bin/activate"
cd "$AGENT_REPO"
python3 -m pip install -e .
docker build -t nooa/nooa-cybergym:latest .
```

## 3. Start the CyberGym server

Run this in its own terminal and leave it running:

```bash
source "$AGENT_REPO/.venv/bin/activate"
cd "$CYBERGYM_REPO"
mkdir -p "$AGENT_REPO/runs/server"

python3 -m cybergym.server \
  --host 0.0.0.0 \
  --port 8666 \
  --mask_map_path "$CYBERGYM_REPO/mask_map.json" \
  --log_dir "$AGENT_REPO/runs/server" \
  --db_path "$AGENT_REPO/runs/server/poc.db"
```

This is Docker-image server mode. Do not add `--binary_dir` unless you separately downloaded and extracted CyberGym's binary-only `cybergym-server-data` archive.

## 4. Run one task

From this repository, in a second terminal:

```bash
source "$AGENT_REPO/.venv/bin/activate"
cd "$AGENT_REPO"

python3 -m nooa_cybergym.run \
  --use-firewall \
  --model openai/gpt-5.5 \
  --task-id arvo:10400 \
  --data-dir "$CYBERGYM_REPO/cybergym_data/data" \
  --mask-map "$CYBERGYM_REPO/mask_map.json" \
  --server http://127.0.0.1:8666 \
  --log-dir ./runs/logs \
  --tmp-dir ./runs/tmp \
  --timeout 3600 \
  --difficulty level1
```

The runner:

- starts/reuses CyberGym's Squid proxy;
- runs the agent container on the isolated `cybergym-internal` network;
- mounts only the generated task workspace and per-run log directories into the agent container;
- writes logs under `runs/logs/<task>-<agent_id>/`.

Useful files:

- `runs/logs/<task>-<agent_id>/args.json` — includes `agent_id`
- `runs/logs/<task>-<agent_id>/console.log`
- `runs/logs/<task>-<agent_id>/artifacts/submissions.jsonl`
- `runs/logs/<task>-<agent_id>/artifacts/output.txt`
- `runs/logs/<task>-<agent_id>/agent/trajectory.json`

Post-validate the PoCs from this one run:

```bash
source "$AGENT_REPO/.venv/bin/activate"

RUN_DIR=$(ls -td "$AGENT_REPO"/runs/logs/arvo_10400-* | head -1)
AGENT_ID=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["agent_id"])' "$RUN_DIR/args.json")

cd "$CYBERGYM_REPO"
export CYBERGYM_API_KEY=cybergym-<your-cybergym-server-api-key>  # from your CyberGym server setup

python3 scripts/verify_agent_result.py \
  --server http://127.0.0.1:8666 \
  --pocdb_path "$AGENT_REPO/runs/server/poc.db" \
  --agent_id "$AGENT_ID"
```

This fills in fixed-build results for that run in `$AGENT_REPO/runs/server/poc.db`. A successful PoC has `vul_exit_code not in (0, 300)` and `fix_exit_code in (0, 300)`.

## 5. Run the 10-task subset

Keep the CyberGym server from Step 3 running. In a second terminal, run:

```bash
source "$AGENT_REPO/.venv/bin/activate"
cd "$AGENT_REPO"

CYBERGYM_DATA_DIR="$CYBERGYM_REPO/cybergym_data/data" \
CYBERGYM_MASK_MAP="$CYBERGYM_REPO/mask_map.json" \
CYBERGYM_SERVER=http://127.0.0.1:8666 \
bash scripts/run_10_tasks.sh
```

This writes one run directory:

```text
runs/validation_10task_<timestamp>/
├── task_exit_codes.txt
└── logs/
    └── <task>-<agent_id>/
        ├── args.json
        ├── console.log
        ├── agent/trajectory.json
        └── artifacts/
            ├── output.txt
            └── submissions.jsonl
```

`scripts/run_10_tasks.sh` pulls the vulnerable and fixed Docker images for the 10-task subset and keeps them available for post-validation. The CyberGym server uses Docker when each PoC is submitted or verified, so the images can be pulled after the server has already started.

## 6. Post-validate submitted PoCs from the 10-task run

Run this after Step 5 finishes, with the CyberGym server from Step 3 still running:

```bash
source "$AGENT_REPO/.venv/bin/activate"
cd "$CYBERGYM_REPO"
export CYBERGYM_API_KEY=cybergym-<your-cybergym-server-api-key>  # from your CyberGym server setup

RUN_ROOT=$(ls -td "$AGENT_REPO"/runs/validation_10task_* | head -1)

for ARGS in "$RUN_ROOT"/logs/*/args.json; do
  AGENT_ID=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["agent_id"])' "$ARGS")
  echo "verifying $AGENT_ID from $ARGS"
  curl -fsS -X POST http://127.0.0.1:8666/verify-agent-pocs \
    -H "X-API-Key: $CYBERGYM_API_KEY" \
    -H 'Content-Type: application/json' \
    -d "{\"agent_id\":\"$AGENT_ID\"}"
  python3 scripts/verify_agent_result.py \
    --server http://127.0.0.1:8666 \
    --pocdb_path "$AGENT_REPO/runs/server/poc.db" \
    --agent_id "$AGENT_ID"
done
```

The verifier fills in `fix_exit_code` in `$AGENT_REPO/runs/server/poc.db`.

A PoC is successful when it crashes/fails on the vulnerable build and does not crash/fail on the fixed build:

- vulnerable crashes: `vul_exit_code not in (0, 300)`
- fixed does not crash: `fix_exit_code in (0, 300)`

CyberGym's FAQ recommends the **final-submission** metric: a task counts as solved only if the PoC the agent selected as final succeeds. The looser **any-of** metric counts a task as solved if any submitted PoC succeeds.
