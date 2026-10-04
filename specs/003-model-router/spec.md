# 003 - Model Router

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define provider-neutral routing from supervisor requests to Agent Workers.

        ## Non-goals

        - Training custom models.
- Embedding provider SDK calls in core orchestration.
- Selecting tools; tools are handled by the Tool System.

        ## Requirements

        1. The router must receive a model work request with required capabilities.
2. The router must choose an Agent Worker through provider-neutral metadata.
3. The router must return a human-readable rationale without hidden reasoning.
4. The router must support fallback candidates.
5. The router must isolate provider-specific configuration in adapters.

        ## Behavior

        - The supervisor requests routing for model work.
- The router filters workers by capability and policy.
- The router ranks available workers by configured strategy.
- The router returns a selected route or a structured failure.

        ## Interfaces and Data Contracts

        - `ModelWorkRequest`: task_id, step_id, capability, input_shape, constraints, policy.
- `WorkerProfile`: worker_id, provider_id, capabilities, limits, cost_class, latency_class, availability.
- `ModelRoute`: worker_id, provider_adapter_id, rationale, fallback_worker_ids, policy_tags.
- `ProviderAdapter`: invoke(request), normalize(response), normalize_error(error).

        ## Error Handling

        - No compatible worker returns `no_route`.
- Provider unavailable returns `provider_unavailable` with fallback eligibility.
- Policy violations return `route_denied`.
- Malformed worker profiles are ignored and logged.

        ## Security

        - Routing must not leak provider secrets.
- Rationales must be concise summaries, not chain-of-thought.
- Provider responses must be normalized before reaching core components.

        ## Acceptance Criteria

        ### Capability Match

Given a request requires tool-use and long context

When matching workers exist

Then the router selects a worker advertising both capabilities.

### Fallback

Given the preferred provider is unavailable

When a compatible fallback exists

Then the router returns the fallback and records the reason.

### No Route

Given no worker satisfies policy

When routing is requested

Then the router returns a structured no-route error.

        ## Tests

        - Unit tests for capability filtering.
- Policy tests for denied routes.
- Fallback tests for unavailable providers.
- Contract tests for provider adapter normalization.

        ## Evaluation

        - Routing accuracy on labeled fixtures.
- Fallback correctness rate.
- Policy violation count must be zero.

        ## Implementation Tasks

        - [ ] Define worker profile schema.
- [ ] Define model work request and route result.
- [ ] Implement routing policy hooks.
- [ ] Implement provider adapter boundary.

        ## Dependencies

        Depends on `000-foundation`, `001-agent-core`, and `002-task-state`.
