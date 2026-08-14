# CyberGym full OO GLM-5.2 submission metrics

Computed from the base run and retries 1–6. For each of the 1,507 unique tasks,
only its highest-numbered retry is selected. All latest attempts count: reward 1
without an exception is success; reward 0, missing reward, or any trial
exception is failure. No latest attempt was excluded for missing usage metrics.

The token, cost, timing, and request figures are per-attempt averages over all
1,507 attempted tasks.

| Metric | Value | Comment |
|---|---:|---|
| Success rate | 85.3% | 1,286 successful latest attempts / 1,507 attempts. |
| Tasks attempted | 1,507 | All unique tasks, using only the latest attempt. |
| Tasks succeeded | 1,286 | Reward 1 with no trial exception. |
| Tasks failed | 221 | Reward 0, missing reward, or trial exception. |
| Input tokens | 11,434,221 | Average non-cached prompt tokens per attempt. |
| Cache read tokens | 53,169,469 | Average cached prompt tokens per attempt. |
| Output tokens | 573,441 | Average generated tokens per attempt. |
| Provider-reported cost (USD) | $4.60 | Average available billing telemetry; Nemotron usage is unpriced. |
| Wall-clock time (min) | 58 | Average start-to-finish time, including setup and verification. |
| LLM requests | 765.1 | Average completed NOOA journal call records per attempt. |

## Per-model token breakdown

| Model | Input tokens | Cache read tokens | Output tokens | LLM requests |
|---|---:|---:|---:|---:|
| `nvidia/deepseek-ai/deepseek-v4-flash` | 1,610,922 | 11,474,295 | 210,060 | 153.7 |
| `nvidia/nvidia/nemotron-3-ultra` | 7,912,526 | 14,961,000 | 129,920 | 223.9 |
| `nvidia/zai-org/glm-5.2` | 1,910,605 | 26,731,425 | 233,550 | 387.5 |
| `result.json` minus completed journal calls | 169 | 2,749 | -88 | — |

The final row is the small reconciliation delta between `result.json` token
accounting and completed journal calls. Provider cost includes positive billing
telemetry returned for GLM-5.2 and DeepSeek; Nemotron returned token counts but
no cost.

Selected latest attempts by retry number: base 1,284; retry1 138; retry2 27;
retry3 22; retry4 8; retry5 5; retry6 23.
