# Contributing Guide

## Before you start

Read [architecture.md](architecture.md) and [coding-standards.md](coding-standards.md) —
PRs that don't respect the layering (e.g. a router calling the database
directly) will be asked to change.

## Workflow

1. Check/open an issue describing the change.
2. Branch from `develop` (see [branching-strategy.md](branching-strategy.md)).
3. Keep PRs scoped to one concern — a bug fix doesn't need a refactor riding
   along with it.
4. Write or update tests for anything you touch. Untested business logic
   doesn't merge.
5. Run the full local check before opening a PR:
   ```bash
   pre-commit run --all-files
   (cd backend && pytest)
   (cd frontend && npm run test && npm run typecheck)
   ```
6. Open the PR against `develop` with a clear description of *why*, not just
   *what* (the diff already shows what).
7. Address review feedback with new commits — don't force-push over a
   review in progress; squash happens at merge time.

## Commit messages

Conventional Commits, enforced by commitlint via Husky — see
[git-workflow.md](git-workflow.md#commit-message-format).

## Code review expectations

- Reviewers check: correctness, layering (does this belong in this layer?),
  test coverage, and whether the change matches the module's declared scope
  (see each module's "STOP after Module N" boundary in its prompt/issue).
- Out-of-scope additions (e.g. sneaking in an auth endpoint during a
  foundation PR) get pushed back, even if the code is otherwise fine —
  scope creep between modules makes the module boundaries meaningless.

## Reporting bugs / requesting features

Use the repository issue tracker. Include repro steps for bugs; for
features, state the problem before proposing the solution.
