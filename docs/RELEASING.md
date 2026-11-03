# Releasing headroid

The `release` workflow (`.github/workflows/release.yml`) builds the device-server jar, tests the host package, builds
the wheel with the jar inside, and checks it with `twine check --strict`. On a `v*` tag it also attaches the wheel and
the jar to a GitHub release and publishes the wheel to PyPI.

PyPI publishing uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/): no API token is stored anywhere.
Only the wheel is published; an sdist could not carry the prebuilt jar.

## One-time setup (owner)

1. Create an account on [pypi.org](https://pypi.org/account/register/) and turn on two-factor authentication.
2. Open [Publishing](https://pypi.org/manage/account/publishing/) and add a **pending publisher** (GitHub tab):
   - PyPI Project Name: `headroid`
   - Owner: `anand-s-kale`
   - Repository name: `headroid`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. On GitHub, repository **Settings → Environments → New environment** named `pypi`. Optional but recommended: add
   yourself under **Required reviewers**, so every publish waits for your click.

## Each release

1. Set the version in `packages/headroid/pyproject.toml` and `packages/headroid/src/headroid/__init__.py`
   (alpha: `0.1.0a1`, `0.1.0a2`, ...; final: `0.1.0`). The workflow refuses a tag that does not match.
2. Move the `[Unreleased]` entries of `CHANGELOG.md` under the new version.
3. Commit, then tag and push: `git tag v0.1.0a1 && git push origin v0.1.0a1`.
4. Approve the `pypi` environment in the Actions run if you set a reviewer.
5. Check `pip install --pre headroid` in a clean virtual environment, then `headroid doctor` on a phone.

A version can never be uploaded twice to PyPI, even after deleting it: fix forward with the next version number.
