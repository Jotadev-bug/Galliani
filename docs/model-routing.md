# Model Routing

Galliani routes work to Agent Workers through provider-neutral model contracts.

## Routing Inputs

- Task type.
- Required capabilities.
- Context size.
- Latency target.
- Cost target.
- Reliability target.
- Tool-use requirements.
- User or project policy.
- Provider availability.

## Routing Output

The router returns a `ModelRoute` containing:

- Worker identifier.
- Provider adapter identifier.
- Capability match.
- Policy decision.
- Human-readable rationale.

The rationale must explain practical selection factors without exposing chain-of-thought.

## Provider Adapters

Provider adapters translate a Galliani model request into provider-specific calls. Core orchestration must never depend on provider-native response shapes.

## Fallbacks

If a worker is unavailable, the router may select a fallback with compatible capabilities. Fallbacks must be recorded in Task State and Observability.
