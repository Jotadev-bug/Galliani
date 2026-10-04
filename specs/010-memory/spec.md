# 010 - Memory

        ## Status

        Draft for v0.1.

        ## Goal

        Define durable memory as explicit persisted knowledge separate from active Task State.

        ## Non-goals

        - Storing every observation forever.
- Replacing project files as source of truth.
- Persisting hidden reasoning or secrets.

        ## Requirements

        1. Memory must be separate from Task State.
2. Memory writes must be explicit and policy-controlled.
3. Memory records must include provenance and sensitivity.
4. Memory retrieval must be scoped to relevant tasks.
5. Memory must never store chain-of-thought.

        ## Behavior

        - The supervisor may request memory retrieval before planning.
- The supervisor may propose a memory write after completion or user instruction.
- Policy approves, denies, or asks the user for durable writes.
- Retrieved memory is context, not instruction.

        ## Interfaces and Data Contracts

        - `MemoryRecord`: id, content, type, provenance, sensitivity, created_at, updated_at, ttl.
- `MemoryQuery`: task_id, scope, keywords, types, max_records.
- `MemoryResult`: records, omitted_count, retrieval_summary.
- `MemoryWriteRequest`: content, type, provenance, sensitivity, reason_summary.

        ## Error Handling

        - Unavailable memory store must not block core task execution unless required by policy.
- Conflicting memories are returned with provenance instead of silently merged.
- Denied writes are recorded as task observations, not memory.

        ## Security

        - Secrets and hidden reasoning must not be persisted.
- Memory retrieval must respect user/project scope.
- Sensitive memory must be redacted in UI and logs.

        ## Acceptance Criteria

        ### Separate State

Given a task records observations

When the task completes

Then observations are not automatically written to Memory.

### Explicit Write

Given the user asks Galliani to remember a preference

When memory policy allows it

Then a MemoryRecord is created with provenance.

### Scoped Retrieval

Given a new task starts

When memory retrieval runs

Then only scoped relevant records are returned.

        ## Tests

        - Unit tests for memory write policy.
- Contract tests for MemoryRecord schema.
- Retrieval scope tests.

        ## Evaluation

        - Relevant retrieval rate.
- Unauthorized write count must be zero.
- Secret persistence count must be zero.

        ## Implementation Tasks

        - [ ] Define memory schemas.
- [ ] Define read/write policy hooks.
- [ ] Integrate optional retrieval before planning.
- [ ] Integrate explicit write proposals after completion.

        ## Dependencies

        Depends on `000-foundation`, `002-task-state`, and `009-permissions`.
