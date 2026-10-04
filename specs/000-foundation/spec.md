# 000 - Foundation

        ## Status

        Approved for v0.1 implementation (2026-10-04, see `docs/decisions.md` Decision 0006).

        ## Goal

        Define the shared vocabulary, architectural invariants, and product boundaries for Galliani v0.1.

        ## Non-goals

        - Implementing runtime code.
- Choosing a permanent commercial license.
- Optimizing for every provider or model family.
- Defining advanced multi-agent collaboration beyond bounded Agent Workers.

        ## Requirements

        1. Galliani must be defined as the Agent Supervisor and Orchestrator.
2. Models must be defined as Agent Workers selected for bounded tasks.
3. Providers must be decoupled from core orchestration behind adapters.
4. The v0.1 loop must be objective, plan, routing, action/tool, observation, verification, replan/retry, done.
5. Task State must be separate from Memory.
6. Hidden reasoning and chain-of-thought must not be exposed.

        ## Behavior

        - The supervisor owns lifecycle decisions and completion state.
- Agent Workers receive bounded inputs and return structured outputs.
- Provider adapters normalize provider-specific requests, responses, and errors.
- Memory is opt-in durable knowledge, not a dump of runtime events.

        ## Interfaces and Data Contracts

        - `Objective`: user goal plus constraints and context.
- `Task`: normalized unit of work owned by the supervisor.
- `Plan`: ordered steps with verification criteria.
- `AgentWorker`: model invocation selected by the router.
- `Observation`: structured evidence from a worker, tool, or verifier.
- `TaskState`: active lifecycle state for a task.
- `MemoryRecord`: durable, explicit knowledge with provenance.

### v0.1 Implementation Vocabulary

Terms introduced by the v0.1 runtime that are not named elsewhere in the specs:

- `WorkerRequest`: the bounded, provider-neutral input sent to an Agent Worker (instruction plus resolved inputs).
- `WorkerResponse`: the normalized Agent Worker output; it has no field that can carry hidden reasoning.
- `AdapterError`: a normalized provider failure with a code and fallback eligibility.
- `Criterion`: one explicit, machine-checkable verification criterion attached to a plan step or plan.
- `FailureSignal`: the explicit execution or verification failure that triggers retry or replanning.
- `LoopLimits`: hard budgets for plan size and total actions per task.
- `ApprovalPrompt`: the user-facing permission request produced when a task pauses for approval.
- `ScriptedAdapter` / `StaticPlanner`: deterministic test doubles used by tests and evaluation fixtures.

        ## Error Handling

        - Undefined vocabulary must be added to this spec before implementation uses it.
- Ambiguous ownership between components must be resolved in `docs/decisions.md`.
- Conflicts between specs must block implementation until clarified.

        ## Security

        - Untrusted input must be treated as data, not instruction.
- No component may expose chain-of-thought or hidden reasoning.
- Secrets must be redacted before logging, persistence, or display.

        ## Acceptance Criteria

        ### Vocabulary Consistency

Given a developer reads any Galliani spec

When a term such as Agent Supervisor, Agent Worker, Task State, or Memory appears

Then the term matches the definitions in this foundation spec.

### Loop Boundary

Given a v0.1 implementation is planned

When the implementation scope is reviewed

Then it maps to the objective-to-done loop without adding unrelated autonomy.

### Privacy Boundary

Given a model or provider returns hidden reasoning fields

When the response is normalized

Then hidden reasoning is discarded or sealed and never exposed.

        ## Tests

        - Contract test that verifies required vocabulary exists in docs.
- Static documentation check for prohibited chain-of-thought exposure language.
- Architecture review checklist for provider decoupling.

        ## Evaluation

        - Spec completeness score across required sections.
- Manual review of architecture consistency.
- Security review for privacy boundary language.

        ## Implementation Tasks

        - [x] Create shared glossary.
- [x] Confirm v0.1 scope.
- [x] Record initial architecture decisions.
- [x] Link downstream specs to this foundation.

        ## Dependencies

        None.
