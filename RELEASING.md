# Releasing

Four workspace packages release together from the same git commit:

- **`nooa`** — the core framework
- **`nooa-cli`** — the `nooa` command and REPL
- **`nooa-memory`** — the long-term memory subsystem
- **`nooa-bench`** — the benchmark agent and Harbor runner

The version is derived from the git **tag** at build time by
[`uv-dynamic-versioning`](https://github.com/ninoseki/uv-dynamic-versioning).
There is no `version = "..."` in any `pyproject.toml` and no manual bump step.
**Tagging the commit is the release ceremony.**

## Versioning

The version comes from the last `vX.Y.Z` tag reachable from the commit, plus
the distance to that tag:

| Repo state | Version |
|---|---|
| Exactly on tag `v0.0.6` | `0.0.6` |
| 5 commits past `v0.0.6` | `0.0.7.dev5` |
| No `vX.Y.Z` tag reachable yet | `0.0.1.dev<distance>` |

> `fallback-version = "0.0.6"` in `pyproject.toml` is used **only** when git
> is unavailable (e.g. building from an unpacked sdist with no `.git/`).
> Whenever git is present, the version is derived from `git describe`.

This is a `0.x` **research preview** — the public API is not yet stable and may
change between releases (per [SemVer](https://semver.org/), `0.y.z` signals
initial development).

## Cutting a release

```bash
git checkout main && git pull
git tag -a v0.0.6 -m "NOOA 0.0.6 — research preview"
git push origin v0.0.6
```

Build the four packages from the tagged commit:

```bash
rm -rf dist
for p in nooa nooa-cli nooa-memory nooa-bench; do
  uv build --package "$p" --out-dir dist
done
```

**Smoke-test the wheels in a clean environment** before publishing:

```bash
python3.12 -m venv /tmp/nooa-smoke && . /tmp/nooa-smoke/bin/activate
pip install dist/nooa-*.whl dist/nooa_cli-*.whl dist/nooa_memory-*.whl dist/nooa_bench-*.whl
python -c "import nooa, nooa_cli, nooa_memory, nooa_bench; print(nooa.__version__)"
nooa --version
deactivate
```

### Pre-release tags

Annotated tags like `v0.0.6-rc1` build as `0.0.6rc1` (PEP 440 normalized).

## Distribution

The packages are currently distributed as **source** — install directly from
GitHub at a tag:

```bash
uv add "nooa @ git+https://github.com/NVIDIA-NeMo/labs-OO-Agents.git@v0.0.6"
```

Optionally attach the built wheels to a **GitHub Release** for the tag.

> **PyPI publishing is not yet enabled.** When it is, a GitHub Actions workflow
> (PyPI Trusted Publishing) will build and upload all four packages on each
> `vX.Y.Z` tag. The names `nooa`, `nooa-cli`, `nooa-memory`, and `nooa-bench`
> are available on PyPI and can be reserved ahead of the first publish.

## Cross-package dependencies

`nooa-cli`, `nooa-memory`, and `nooa-bench` depend on the core `nooa` package.
They are always released together at the same derived version, so their
dependency on `nooa` carries **no version floor** — CI never rewrites it.
