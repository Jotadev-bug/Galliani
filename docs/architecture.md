# Architecture

Galliani is organized around a single responsibility: supervise AI work until a user objective is completed or safely stopped.

## High-Level Flow

```text
User Objective
     |
     v
Agent Supervisor
     |
     +--> Planner
     +--> Model Router
     +--> Execution Engine
     +--> Tool System
     +--> Verification
     +--> Replanning
     +--> Task State
     +--> Memory
     `--> Observability
```

## Core Components

### Agent Supervisor

Owns the lifecycle. It decides what happens next, not the worker model.

### Planner

Converts objectives into explicit steps with success conditions.

### Model Router

Selects an Agent Worker and provider adapter based on task needs, policy, availability, and cost/quality constraints.

### Execution Engine

Runs plan steps, invokes models and tools, records observations, and hands results to verification.

### Tool System

Registers tools, validates input schemas, checks permissions, executes calls, and returns structured results.

### Verification

Determines whether outputs satisfy the current step and overall objective.

### Replanning

Responds to failed verification, blocked tools, worker errors, or changed user constraints.

### Task State

Stores active execution state for a single task or run.

### Memory

Stores durable facts, preferences, and project knowledge that are intentionally persisted.

## Provider Decoupling

Core orchestration must depend on provider-neutral interfaces. Provider adapters translate Galliani contracts into provider-specific requests and responses.

## Front Ends (Wiring Layers)

Front ends connect real providers and tools to the supervisor and show its public events. Core modules never import them.

- `galliani/cli/`: one-shot command (Decision 0015).
- `galliani/tui/`: interactive terminal session (spec 017, Decision 0034). A headless controller drives the supervisor; only its Textual modules import Textual.
- `app/`: desktop app and local API (spec 012).

## Privacy Boundary

Galliani may store summaries, decisions, observations, and final answers. It must not expose or persist chain-of-thought, hidden reasoning traces, or private model scratchpads.
