"""AgentRunner seam for substrate adapters.

This module defines the piece of the live runner contract that adapters
depend on: the abstract ``AgentRunner`` seam real substrates (Backgammon,
SWE-ContextBench) implement.

The ``TaskOutcome`` telemetry dataclass and the ``run_task`` abstract method
were removed with LI-4: memory reinjection is worker-side via the plugin,
never an ``injected_memory`` parameter on a runner seam, and ``run_task``
had no callers.

The retired OFF/ON ablation driver (``run_ablation``) and its helpers
(``MockAgentRunner``, ``_cell_from_outcome``, ``_log_cell``, ``_session_id``)
were removed with WO-DEADPATH-1: they had no live entrypoint.
"""

from __future__ import annotations

import abc


class AgentRunner(abc.ABC):
    """Seam for substrate adapters (Aider polyglot, SWE-ContextBench — built in a LATER task)."""
