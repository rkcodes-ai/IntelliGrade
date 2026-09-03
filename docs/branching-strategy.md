# Branching Strategy

A simplified Git Flow, sized for a small team building this incrementally
module by module.

## Branches

| Branch          | Purpose                                                        | Protected |
|-------------------|------------------------------------------------------------------|-----------|
| `main`              | Always deployable. Only receives merges from `develop` via release PRs. | Yes |
| `develop`             | Integration branch. Feature branches merge here first.                | Yes |
| `feature/<slug>`        | New functionality. Branches from and merges back into `develop`.    | No  |
| `fix/<slug>`               | Bug fixes not urgent enough for a hotfix.                          | No  |
| `hotfix/<slug>`              | Urgent production fix. Branches from `main`, merges into both `main` and `develop`. | No |
| `chore/<slug>`                 | Tooling, CI, dependency, docs-only changes.                       | No  |

## Naming

`<type>/<short-kebab-case-description>`, e.g. `feature/answer-script-upload`,
`fix/health-check-timeout`, `chore/upgrade-fastapi`.

Optionally prefix with a ticket/module reference if your tracker uses one,
e.g. `feature/module-02-auth-jwt-login`.

## Lifecycle

1. Branch from `develop` (or `main` for `hotfix/*`).
2. Commit using [Conventional Commits](git-workflow.md#commit-message-format).
3. Open a PR back into the source branch. CI must pass.
4. Squash-merge. Delete the branch after merge.
5. Periodically, `develop` is merged into `main` via a release PR when a
   module milestone is deployable.

## Module boundaries and branches

Each numbered module (Module 01 foundation, Module 02 auth, ...) is
expected to land as one or more PRs scoped strictly to that module's stated
deliverables — see each module's "STOP after Module N" instruction. Don't
let a Module 02 branch quietly grow Module 03 functionality; open a new
branch instead.
