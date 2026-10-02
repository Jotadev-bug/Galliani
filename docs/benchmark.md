# Benchmark

## Method

1. **Matrix.** Every task runs once on every candidate model (`max_tokens` 4096, provider-default
   temperature) and is graded by automatic checks in `benchmarks/evaluate.py`. Responses are cached
   in `benchmarks/results/cache/`.
2. **Routing.** Each router picks a model per task, and its outcome is looked up in the matrix. If the
   chosen model errored, the router's fallback chain is followed, as the live executor would.
   Because every router is graded on the same responses, the comparison is fair, and new weights or
   routers can be evaluated without calling any model again.
3. **Oracle.** The cheapest model that actually passed each task. This is the upper bound on what
   any router could save on this task set.

Routers compared: `frontier` (baseline, experiment #1), `jeb`, `random` (experiment #2), `rules`
(experiment #3) and `cheapest`. Routing overhead (experiment #4) is reported as the selector's
cost and latency, and as a share of gross savings.

## Tasks

There are 67 tasks in `benchmarks/tasks.yaml` across 13 categories, in English and Spanish, ranging
from trivial to hard. Graders are deterministic: substrings, regexes, `Answer:` parsing, JSON
equality, word/line/paragraph counts, Python unit tests, SQL result comparison, and custom
validators. Every task carries a reference answer, and the test suite checks that each reference
passes and that a non-answer fails.

Python and SQL checks **execute model-generated code**: Python runs in an isolated subprocess with a
10 s timeout, and SQL runs in an in-memory SQLite connection with ATTACH denied. Use `--no-exec`
to skip those tasks.

Gaps: no multimodal or tool-use tasks yet, open-ended writing quality is only checked for form,
and 67 tasks is below the 100–300 that PROJECT.md §16 targets.

## Reading the report

- **Quality** is the mean fraction of checks passed. **Success** means every check passed.
- **Savings** is `1 − cost_router / cost_frontier`, with routing cost included.
- **d.qual** is the quality difference from the frontier baseline, in percentage points.
- **Calibration** compares JEB's stated confidence with actual success, by band.
- The full JSON report (`benchmarks/results/report-*.json`) contains the whole matrix, per-model
  scores, per-category results and every routing decision.

`--simulate` replaces models with a seeded coin flip weighted by skill and difficulty. It only
tests the pipeline. **Its numbers mean nothing.**
