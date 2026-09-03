# Git Workflow

See [branching-strategy.md](branching-strategy.md) for branch naming/lifecycle.

## Commit message format

[Conventional Commits](https://www.conventionalcommits.org/), enforced by
commitlint via a Husky `commit-msg` hook (`commitlint.config.js`):

```
<type>(<optional scope>): <short summary>

<optional body — the WHY>
```

Allowed types: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
`build`, `ci`, `chore`, `revert`.

Examples:
```
feat(backend): add readiness probe with DB/Redis checks
fix(frontend): correct dark mode flash on initial load
docs: add database migration conventions
```

## Pull requests

- One PR = one logical change. Rebase/squash locally before opening if your
  branch has "wip" commits — the merged history should read as intentional.
- PR description states the *why* (see [contributing.md](contributing.md)).
- CI (`lint.yml`, `test.yml`, `build.yml`, `docker.yml`) must pass before
  merge.
- Squash-merge into `develop` by default, so `develop`'s history stays one
  commit per PR.

## Keeping history clean

- Never force-push a shared branch (`main`, `develop`) — see
  [branching-strategy.md](branching-strategy.md).
- Prefer `git rebase` over `git merge` when catching a feature branch up
  with `develop`, unless the branch is already shared with someone else
  (then merge, to avoid rewriting commits they've based work on).
