# BrewAssistant development workflow

BrewAssistant intentionally uses only three long-lived branches.

```text
dev  ->  beta  ->  main  ->  GitHub Release
```

## Branch roles

### `dev`

Active development branch.

- All normal BrewAssistant code, dashboard and documentation work starts here.
- Direct project work is committed to `dev`.
- Dependabot targets `dev`.
- CI, HACS validation and Hassfest run on every push.
- Do not create persistent feature/fix branches in this repository.

External contributors may use a fork and open a pull request against `dev`.

### `beta`

Integration and field-test branch.

- Receives promotion only from `dev`.
- Used for a coherent beta candidate after the current `dev` state is ready for practical Home Assistant/BrewZilla testing.
- No unrelated development is performed directly on `beta`.
- CI, HACS validation and Hassfest must be green before promotion continues.

### `main`

Installable/runnable branch.

- Receives promotion only from `beta`.
- Represents the current version considered safe enough to install and run.
- No normal development is performed directly on `main`.
- A promotion to `main` should correspond to a versioned GitHub Release.

## Promotion flow

```text
work and regression checks
        |
        v
      dev
        |
        | PR: dev -> beta
        v
      beta
        |
        | practical validation + green watchdogs
        | PR: beta -> main
        v
      main
        |
        | tag + GitHub Release
        v
  released version
```

The repository promotion guard rejects:

- PRs to `beta` from anything other than `dev`
- PRs to `main` from anything other than `beta`

GitHub branch protection/rules should additionally require pull requests for `beta` and `main`, so direct pushes cannot bypass the promotion model.

## Branch cleanup

Only `dev`, `beta` and `main` are long-lived repository branches.

Temporary Dependabot branches may exist while an update pull request is open and should disappear after merge/close. Old development branches should not be retained as archives; merged work is preserved by Git history, pull requests, tags and releases.

## Releases

While BrewAssistant remains beta, use semantic prerelease versions:

```text
v0.2.0-beta.9
v0.2.0-beta.10
...
```

Release rules:

1. Version is prepared on `dev`.
2. `dev` is promoted to `beta`.
3. The beta candidate is validated in Home Assistant and, where relevant, against real brewing hardware.
4. `beta` is promoted to `main`.
5. Create the matching tag and GitHub Release from the resulting `main` commit.
6. Mark beta versions as GitHub prereleases.

Do not create releases from `dev` or `beta`.

When BrewAssistant reaches a non-beta milestone, switch to normal semantic versions such as `v0.2.0` or `v1.0.0`.

## Documentation sync

A promotion candidate should update documentation together with the behavior it describes. In particular, keep these current before promotion to `main`:

- `CHANGELOG.md`
- current release notes under `docs/`
- `docs/roadmap.md`
- relevant backend/architecture documentation
- physical-validation notes after meaningful hardware tests

Historical physical-validation documents are snapshots of what was observed at that date and should not be rewritten to make later behavior look retroactively correct. Add a new dated validation document instead.
