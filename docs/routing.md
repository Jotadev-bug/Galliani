# Routing

## 1. Task profile

A router produces a `TaskProfile`: `task_type`, five requirements in [0, 1] (`reasoning`, `coding`,
`writing`, `knowledge`, `precision`) and `expected_output_tokens`. JEB produces it from the prompt
(`app/router/jeb.py`); the prompt tells the selector not to solve the task, wraps the task in `<task>`
tags and truncates it to 6,000 characters.

## 2. Success estimate

For each candidate:

```text
P(success) = Π_d sigmoid(steepness · (skill_d − requirement_d) + bias)
```

`precision` is checked against the model's `instruction_following` skill. Skills are **priors**
in `config/models.yaml`; `steepness` and `bias` are in `config/routing.yaml`.

## 3. Utility and "sufficiently capable"

```text
Utility = q·P − c·cost_penalty − l·latency_penalty − r·(1 − P)·precision
```

Cost and latency penalties are log-scaled to [0, 1] across the current candidates. Candidates with
`P ≥ min_success` are ranked by utility, and the rest by P. The first one is selected and the rest
form the fallback order. Each mode (`auto`, `cheapest`, `fastest`, `best`) is its own set of weights.

## 4. Confidence policy (JEB only)

| JEB confidence | Action |
|---|---|
| ≥ `execute_threshold` (0.90) | use the routed model |
| ≥ `safer_threshold` (0.70) | move up one tier |
| < `safer_threshold` | use the most capable candidate |

## Calibration: what is still a guess

All of these were set by hand and must be fitted from benchmark data before anyone relies on them:

1. **Model skill priors.** Fit them per model from the benchmark matrix (per-category success rates).
2. **`steepness` and `bias`.** Fit them so the predicted P matches observed success (reliability curve).
3. **Confidence thresholds.** The report's calibration table shows the actual success rate in each
   confidence band. Set the thresholds where success actually changes.
4. **Utility weights.** Sweep them over the cached matrix. This costs nothing, because routing is
   re-evaluated against stored responses.
