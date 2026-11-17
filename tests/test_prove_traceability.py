"""A told line must name exactly one thing: a finding, or a declared block."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import prove


def entry(finding_key=None, declared_class=None):
    return {
        "index": 1,
        "text": "some line",
        "finding_key": finding_key,
        "declared_class": declared_class,
    }


class TraceabilityViolationsTest(unittest.TestCase):
    def test_both_identities_is_a_violation(self):
        violations = prove.traceability_violations([entry("F35", "section-headers")])
        self.assertEqual(len(violations), 1)
        self.assertIn("both", violations[0])

    def test_no_identity_is_a_violation(self):
        violations = prove.traceability_violations([entry()])
        self.assertEqual(len(violations), 1)
        self.assertIn("neither", violations[0])

    def test_well_formed_entries_pass(self):
        self.assertEqual(
            prove.traceability_violations(
                [entry(finding_key="F35.controls"), entry(declared_class="section-headers")]
            ),
            [],
        )


class RecordIntegrityTest(unittest.TestCase):
    """The checked-in baseline itself must be traceable — the proof's own claim."""

    def test_checked_in_builds_name_exactly_one_thing(self):
        builds = prove.load_builds()
        entries, violations = prove.told_identity_counts(builds)
        self.assertGreater(entries, 0)
        self.assertEqual(violations, [])

    def test_every_told_finding_is_cited_and_every_citation_maps_back(self):
        builds = prove.load_builds()
        agreements, violations = prove.citation_counts(builds)
        self.assertGreater(agreements, 0)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
