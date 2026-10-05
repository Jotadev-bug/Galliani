# Contributing to Galliani

Galliani uses spec-driven development. Contributions should start from a spec and end with tested behavior.

## Before You Start

1. Read `README.md`.
2. Read `PROJECT.md`.
3. Read `AGENTS.md`.
4. Read the relevant files under `specs/`.

## Contribution Flow

1. Identify the spec requirement being changed.
2. Update the spec first if behavior is missing or ambiguous.
3. Implement only the approved scope.
4. Add tests tied to acceptance criteria.
5. Update docs and changelog if behavior changes.
6. Explain verification performed.

## Spec Changes

Spec updates should include:

- Status.
- Goal.
- Non-goals.
- Numbered requirements.
- Behavior.
- Interfaces and data contracts.
- Error handling.
- Security.
- Given/When/Then acceptance criteria.
- Tests.
- Evaluation.
- Implementation tasks.
- Dependencies.

## Pull Request Checklist

- The change references one or more specs.
- New behavior has tests.
- Provider-specific code is isolated behind adapters.
- Task State and Memory remain separate.
- Tool calls are permission-aware.
- Logs and outputs do not expose chain-of-thought, secrets, or private scratchpads.
- The changelog is updated when user-visible behavior changes.

## License

Galliani is licensed under the GNU AGPL-3.0 or later (see `LICENSE`). By contributing, you agree that your contribution is licensed under the same terms.

## Communication

Prefer precise issue descriptions, small pull requests, and concrete acceptance criteria. If a decision changes architecture, add it to `docs/decisions.md`.
