#!/usr/bin/env bash
set -euo pipefail

AGENT_REPO="${AGENT_REPO:-$(pwd)}"
cd "$AGENT_REPO"

export PYTHONUNBUFFERED=1

MODEL="${MODEL:-openai/gpt-5.5}"
CYBERGYM_SERVER="${CYBERGYM_SERVER:-http://127.0.0.1:8666}"
CYBERGYM_DATA_DIR="${CYBERGYM_DATA_DIR:-${CYBERGYM_REPO:-$AGENT_REPO/../cybergym}/cybergym_data/data}"
CYBERGYM_MASK_MAP="${CYBERGYM_MASK_MAP:-${CYBERGYM_REPO:-$AGENT_REPO/../cybergym}/mask_map.json}"
RUN_ROOT="${RUN_ROOT:-$AGENT_REPO/runs/validation_10task_$(date +%Y%m%d_%H%M%S)}"
LOG_DIR="${LOG_DIR:-$RUN_ROOT/logs}"
TMP_DIR="${TMP_DIR:-$RUN_ROOT/tmp}"
TIMEOUT="${TIMEOUT:-3600}"
DIFFICULTY="${DIFFICULTY:-level1}"
CLEAN_TASK_IMAGES="${CLEAN_TASK_IMAGES:-0}"
RUNNER_IMAGE="${RUNNER_IMAGE:-nooa/nooa-cybergym:latest}"

DEFAULT_TASKS=(
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
)

if [ "$#" -gt 0 ]; then
  TASKS=("$@")
else
  TASKS=("${DEFAULT_TASKS[@]}")
fi

mkdir -p "$LOG_DIR" "$TMP_DIR"
: > "$RUN_ROOT/task_exit_codes.txt"

image_names_for_task() {
  local task_id="$1"
  local prefix="${task_id%%:*}"
  local id="${task_id##*:}"
  if [ "$prefix" = "arvo" ]; then
    printf 'n132/arvo:%s-vul\n' "$id"
    printf 'n132/arvo:%s-fix\n' "$id"
  elif [ "$prefix" = "oss-fuzz" ]; then
    printf 'cybergym/oss-fuzz-base-runner:latest\n'
    printf 'cybergym/oss-fuzz:%s-vul\n' "$id"
    printf 'cybergym/oss-fuzz:%s-fix\n' "$id"
  fi
}

cleanup_task_images() {
  if [ "$CLEAN_TASK_IMAGES" != "1" ]; then
    return 0
  fi
  local task_id="$1"
  mapfile -t images < <(image_names_for_task "$task_id")
  if [ "${#images[@]}" -gt 0 ]; then
    docker image rm "${images[@]}" >/dev/null 2>&1 || true
  fi
  docker image prune -f >/dev/null 2>&1 || true
}

pull_task_images() {
  local task_id="$1"
  mapfile -t images < <(image_names_for_task "$task_id")
  for image in "${images[@]}"; do
    echo "pull $image"
    docker pull "$image"
  done
}

echo "===== RUN ROOT $RUN_ROOT ====="
echo "===== CHECK SERVER $CYBERGYM_SERVER $(date -Is) ====="
if ! curl -fsS "$CYBERGYM_SERVER/docs" >/dev/null; then
  cat >&2 <<EOF
CyberGym server is not reachable at $CYBERGYM_SERVER.

Start it in another terminal before running this script:

  cd ${CYBERGYM_REPO:-$AGENT_REPO/../cybergym}
  python3 -m cybergym.server \
    --host 0.0.0.0 \
    --port 8666 \
    --mask_map_path "$CYBERGYM_MASK_MAP" \
    --log_dir "$AGENT_REPO/runs/server" \
    --db_path "$AGENT_REPO/runs/server/poc.db"

Then rerun this script. If your server is on another port, set CYBERGYM_SERVER.
EOF
  exit 3
fi

echo "===== BUILD RUNNER IMAGE $(date -Is) ====="
docker build -t "$RUNNER_IMAGE" .

echo "===== RUN ${#TASKS[@]} TASKS $(date -Is) ====="
for TASK_ID in "${TASKS[@]}"; do
  echo "===== START $TASK_ID $(date -Is) ====="
  cleanup_task_images "$TASK_ID"
  pull_task_images "$TASK_ID"

  set +e
  python3 -m nooa_cybergym.run \
    --use-firewall \
    --model "$MODEL" \
    --task-id "$TASK_ID" \
    --data-dir "$CYBERGYM_DATA_DIR" \
    --mask-map "$CYBERGYM_MASK_MAP" \
    --server "$CYBERGYM_SERVER" \
    --log-dir "$LOG_DIR" \
    --tmp-dir "$TMP_DIR" \
    --image "$RUNNER_IMAGE" \
    --timeout "$TIMEOUT" \
    --difficulty "$DIFFICULTY"
  rc=$?
  set -e

  echo "===== END $TASK_ID rc=$rc $(date -Is) ====="
  echo "$TASK_ID $rc" >> "$RUN_ROOT/task_exit_codes.txt"
  cleanup_task_images "$TASK_ID"
done

echo "===== DONE $(date -Is) ====="
echo "run_root=$RUN_ROOT"
echo "task_exit_codes=$RUN_ROOT/task_exit_codes.txt"
