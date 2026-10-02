# Routing

## 1. Task profile

A router produces a `TaskProfile`: `task_type`, five requirements in [0, 1] (`reasoning`, `coding`,
`writing`, `knowledge`, `precision`) and `expected_output_tokens`.

[Jev](https://openrouter.ai/typesafe/jev-1.13) (TypeSafe) is a decision model, not a chat model: it
answers typed questions about a `state` through the OpenRouter Decisions API
(`POST https://openrouter.ai/api/alpha/decisions`) and returns probabilities, never text. One call
per request (`app/router/jev.py`) sends `state = {"user_request": <prompt, max 6,000 chars>}` and asks:

| Question | Type | Becomes |
|---|---|---|
| `model` | Choice over the candidate models | Jev's pick and a probability for each model |
| `task_type` | Choice over 15 task types | `profile.task_type` |
| `reasoning`, `coding`, `writing`, `knowledge`, `precision` | Score over 5 described levels | requirement = score / 4 |
| `output_length` | Score over 4 length buckets | token estimate from `jev.output_tokens_by_level` |
| `sufficient_<tier>` (one per candidate tier) | Noul | P(a model of that tier answers correctly) |

The questions are worded to avoid Jev's documented weak spots
([jaggedness notes](https://docs.typesafe.ai/model-jaggedness/jev-1.13)): every question is literal
and names `user_request`, and no arithmetic or counting is asked of it, so token and cost numbers
are computed in code. Jev bills only input tokens ($0.042/M), and `usage.cost` from the API is
recorded as the routing cost.

Each option in the `model` question is a real model ID with its registry `description`, its exact
price ($ per million input and output tokens), a relative-cost phrase computed in code for this
request ("about 10x the cost of the cheapest option") and a speed label. Options are listed cheapest
first. The instruction depends on the mode (`jev.choice_instructions`). For example, `auto` says
"pick the cheapest model that will answer it completely and correctly".

Three decision styles use the same answers, so the benchmark compares them from one call:

- **`jev-choice`** (default): Jev's pick is used directly. The other models are ordered by Jev's
  probability and become fallbacks, and the Choice's own confidence feeds the confidence policy.
- **`jev-profile`**: the Score answers form the profile, and the utility function below picks the model.
- **`jev-sufficiency`**: the cheapest candidate whose tier Noul is at least `min_success` wins.
  This uses Jev's own probabilities directly, with no skill priors.

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

## 4. Confidence policy (Jev only)

Jev's confidence for the request is the mean of the `confidence` values on its Choice and Score
answers, which describes how concentrated each distribution is. It is **not** a probability that
the routed model succeeds. The benchmark's calibration table shows what it is actually worth.

| Jev confidence | Action |
|---|---|
| ≥ `execute_threshold` (0.90) | use the routed model |
| ≥ `safer_threshold` (0.70) | move up one tier |
| < `safer_threshold` | use the most capable candidate |

## Calibration: what is still a guess

All of these were set by hand and must be fitted from benchmark data before anyone relies on them:

1. **Model skill priors.** Fit them per model from the benchmark matrix (per-category success rates).
2. **`steepness` and `bias`.** Fit them so the predicted P matches observed success (reliability curve).
3. **Jev's sufficiency Nouls.** TypeSafe says Jev is calibrated, but that was measured on their
   tasks, not this one. Compare each tier's Noul against that tier's actual success in the matrix.
4. **Confidence thresholds.** The report's calibration table shows the actual success rate in each
   confidence band. Set the thresholds where success actually changes.
5. **Utility weights.** Sweep them over the cached matrix. This costs nothing, because routing is
   re-evaluated against stored responses.
