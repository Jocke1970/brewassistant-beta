# BrewAssistant development workflow

BrewAssistant uses **only three long-lived branches**:

```text
dev  ->  beta  ->  main
         |        |
         v        v
  GitHub prerelease   Stable GitHub release
```

## Branch roles

### `dev` — development

- All normal code, dashboard, tests, versions and documentation changes start here.
- Commit project work directly to `dev`; Dependabot targets `dev`.
- Release-watchdogs körs inte automatiskt på `dev`. Promotion sker först till `beta`; CI, HACS, Hassfest och den isolerade HA+RCL-smoken verifieras på den faktiska beta-kandidaten.
- Do not create extra project branches. External contributors may use forks targeting `dev`.

### `beta` — installable field-test candidate and prerelease source

- Receives changes **only** from `dev` using a PR and **Create a merge commit**.
- Contains the coherent beta candidate to install via HACS for supervised tests.
- No unrelated development directly on `beta`; fix failures on `dev`, then promote again.
- CI, HACS validation and Hassfest must pass on the actual `beta` merge commit before tagging.
- GitHub tags `vX.Y.Z-beta.N` and their **Pre-release** publications point to the tested `beta` commit, never `dev` or an older branch head.

### `main` — validated/stable distribution

- Receives validated changes only from `beta` using a PR and **Create a merge commit**.
- Do not promote a beta merely because CI is green: complete the required supervised field-test protocol first.
- Stable tags such as `v0.2.0` originate from the verified `main` merge commit and are published as normal GitHub releases.
- Never do unrelated development directly on `main`.

## Promotion and release flow

```text
develop + review + doc-sync
       |
      dev
       | PR dev -> beta; Create a merge commit
       v
      beta
       | CI + HACS + Hassfest + HA/RCL smoke on beta merge SHA
       | tag vX.Y.Z-beta.N AT THIS EXACT beta SHA
       | GitHub Release: target beta, Pre-release = yes
       v
HACS beta install -> supervised water-only / field validation
       | failure: fix dev; promote and issue a NEW beta version
       | validation PASS + stable-release decision
       v
PR beta -> main; Create a merge commit
       |
      main
       | verified stable-version manifest, tag at main SHA
       v
Normal GitHub Release (not a prerelease)
```

**Beta release is required before the physical beta field test:** without a correctly tagged GitHub prerelease, HACS can install the wrong/default-branch code. A published prerelease is an experimental distribution, **not** proof of hardware safety or approval for malt/unattended operation.

### Promotion merge method and repository settings

For both `dev -> beta` and `beta -> main`, use **Create a merge commit** to preserve ancestry. Do not squash or rebase permanent promotion sources. Keep **Automatically delete head branches** disabled; `dev` and `beta` are permanent. Branch protection/rules should require PRs for `beta` and `main`. The promotion guard requires PRs to `beta` from `dev`, and PRs to `main` from `beta`.

## Release checklist — mandatory, every version

1. On `dev`, update integration `manifest.json`, complete release Markdown, relevant Swedish/English cards and test instructions **before** promotion. Historical test reports remain unchanged; add new dated evidence instead.
2. Open/review a `dev -> beta` PR and its entire diff, then promote with **Create a merge commit**. Do not delete `dev`. Release-watchdogs on `dev` are not the acceptance gate.
3. Note the resulting **beta merge commit SHA**. Require CI (Python 3.11, 3.12, 3.13), HACS, Hassfest and the isolated HA/RCL smoke **on that exact SHA**. Verify that manifest version, required control/safety code and release notes are present in `beta` before any installation or field test.
4. Create a **new** tag `vX.Y.Z-beta.N` from the exact beta merge SHA. In the GitHub release form set **Target = beta**, select the intended commit/tag, paste the **entire** Markdown file, mark **Set as a pre-release**, and do not mark it latest/stable.
5. **After publication**, fetch the tag's actual commit SHA, tagged `manifest.json` and critical integration files. Require all to match the validated beta SHA and version. Verify that the release's tag and title agree; do not infer package identity from release prose alone.
6. Back up HA integration/dashboard, install **that exact tag** via HACS with beta versions enabled, restart HA and independently install the manually pasted dashboard cards from the **same tag**. Verify expected entities/attributes, pump/heater OFF, freshness and ABORT before initiating a supervised water-only field test.
7. If any check or test fails, stop, record findings, correct **on `dev`**, promote again and use a **new** beta.N+1 tag. Never rewrite/move a published tag or silently replace its archive. Do not promote to `main` until the relevant field evidence passes.

### Stable release

After appropriate successful field validation, prepare the intended stable version on `dev`, promote it via `beta -> main` with a merge commit and require the validations on the final `main` SHA. Create a distinct stable tag from that `main` SHA and publish a normal GitHub release. Do not move an existing beta tag to `main` or re-label an untested beta as stable.

### Historical mistake: beta.10

`v0.2.0-beta.10` was published from an old `beta` commit with a `beta.9` manifest and without the physical mash interlock, despite its release description. Keep the old tag for traceability; **do not install it for the mash test or retarget it**. The corrective candidate is `v0.2.0-beta.11`, which must first be promoted to `beta` and then checked by tag SHA and tagged files as above.

## Branch cleanup and documentation

Only `dev`, `beta`, `main` are long-lived project branches. Contributor/Dependabot branches may be removed after their work is reviewed/merged; do not delete anything with independent changes. Keep version history in tags/releases, not archive branches. Documentation that describes a candidate must be synchronized with its actual code and release route; update `README.md`, `CHANGELOG.md`, current release notes, `docs/roadmap.md`, relevant backend/dashboard docs and new physical-validation reports. Historical physical-test reports must not be rewritten retroactively.
