# Config migration guide — nooa 0.4.x → 0.5.0

**Applies to:** upgrading from any `nooa < 0.5.0` (e.g. 0.4.7) to
**0.5.0**. The config changes below are **breaking** — that's why they land in
the 0.5.0 minor bump. If you're a fresh `>= 0.5.0` install, there's nothing to
migrate (the installer + first-run scaffold set everything up).

As of 0.5.0, all config lives in **one location, one format (YAML), one
precedence chain** (bundled defaults → user → project → env override, last
wins). Here's everything you need to move.

## 1. Directories renamed

| | Before | After |
|---|--------|-------|
| User-global | `~/.config/nat/oo/` | `~/.config/nooa/` (XDG-aware, all platforms) |
| Project-local | `<project>/.nooa/` | `<project>/.nooa/` |

`NAT_CONFIG_DIR` is gone — use `NEMO_OO_USER_DIR` to relocate the user dir.

## 2. API keys / secrets

| Before | After |
|--------|-------|
| `export NVIDIA_INFERENCE_API_KEY=…` in your shell rc | `secrets.yaml`, auto-loaded by the CLI on every run |

```yaml
# ~/.config/nooa/secrets.yaml   (chmod 600)
env:
  NVIDIA_INFERENCE_API_KEY: sk-...
  # ANTHROPIC_API_KEY: sk-ant-...
```

A shell `export` still wins (non-clobber), so existing exports keep working —
`secrets.yaml` just means you no longer *need* one. The installer writes this
file for you.

## 3. LLM aliases: `llm_config.yaml`

Same filename and format — just move it to the new dir:
`~/.config/nat/oo/llm_config.yaml` → `~/.config/nooa/llm_config.yaml`
(or `<project>/.nooa/llm_config.yaml`). `nooa config eject` regenerates
a fresh copy in the new location.

## 4. Environment variables → `NEMO_OO_` prefix

| Before | After |
|--------|-------|
| `NEMO_RICH_URL` | `NEMO_OO_RICH_URL` |
| `VIEWER_PORT` / `TRACE_VIEWER_PORT` | `NEMO_OO_TRACE_VIEWER_PORT` |
| `TRACE_STORE_DB` | `NEMO_OO_TRACE_DB` |

(`NEMO_OO_LLM_CONFIG`, `NEMO_OO_SETTINGS`, `NEMO_OO_SECRETS`,
`NEMO_OO_USER_DIR`, `NEMO_OO_PROJECT_DIR` are unchanged.)

## Verify

```bash
nooa config show   # shows which settings.yaml / secrets.yaml / llm_config.yaml
                      # layers are active (secret values redacted)
```
