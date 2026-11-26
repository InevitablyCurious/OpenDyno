"""The TWO producers of a cell's variant directory must agree byte for byte.

A cell is WRITTEN under ``<runs>/<variantA|variantB|variantUNKNOWN>/cell-NNNN``
by ``scripts/run_cumulative/paths.py:_variant_dir`` and READ back through
``harness/outcomes/predicate_emitter.py:_variant_dir``. They are separate
implementations — the harness never imports from ``scripts/`` — so a rename that
touched one and not the other would file every later cell where the reader does
not look, and the outcomes would silently record as not-state-bound. This test
exists to make that divergence fail loudly instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# LI-14: run_cumulative is a package (scripts/run_cumulative/) fronted by a thin
# scripts/run_cumulative.py entrypoint; `paths` is imported as a module of that
# package, which is how the writer's helper is pinned here.
sys.path.insert(
    0, str(Path(__file__).resolve().parents[1] / "scripts" / "run_cumulative")
)
from paths import _variant_dir as _paths_variant_dir  # noqa: E402

from harness.outcomes.predicate_emitter import (  # noqa: E402
    _variant_dir as _emitter_variant_dir,
)

# The third bucket is deliberate: a variant that did not resolve must never be
# filed under one of the two real arms.
CASES = (
    ("a", "variantA"),
    ("b", "variantB"),
    ("z", "variantUNKNOWN"),
)


@pytest.mark.parametrize(("variant", "expected"), CASES)
def test_both_producers_name_the_same_directory(variant: str, expected: str) -> None:
    assert _paths_variant_dir(variant) == expected
    assert _emitter_variant_dir(variant) == expected
