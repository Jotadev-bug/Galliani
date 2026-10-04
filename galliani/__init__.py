"""Galliani: a provider-neutral Agent Supervisor.

The supervisor owns the v0.1 loop (spec 000 R4):
objective -> plan -> routing -> action/tool -> observation -> verification -> replan/retry -> done.
Nothing in this package imports provider SDKs or the legacy `app` package (Decision 0009).
"""

__version__ = "0.1.0"
