import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "judge-stats.py")
spec = importlib.util.spec_from_file_location("judge_stats", SCRIPT)
judge_stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(judge_stats)


def fix(ticket, *verdicts, green=True, prs=()):
    return {"kind": "fix", "ticket": ticket, "own_tests_green": green,
            "rounds": [{"verdict": v, "satisfaction": 0.5} for v in verdicts], "prs": list(prs)}


def retest(ticket, verdict, judge="satisfied", green=True):
    return {"kind": "retest", "ticket": ticket, "verdict": verdict, "judge": judge, "own_tests_green": green}


def log(*records):
    """Numbers records in log order, as load() does."""
    for n, r in enumerate(records, 1):
        r["_order"] = n
    return list(records)


def states(mapping):
    return lambda url: (mapping.get(url), None if url in mapping else "not found")


def run(lines, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines))
    try:
        return subprocess.run([sys.executable, SCRIPT, f.name, *args], capture_output=True, text=True)
    finally:
        os.unlink(f.name)


class JudgeStatsTest(unittest.TestCase):
    def test_catch_counts_only_green_runs_rejected_first(self):
        out = judge_stats.summarize(log(
            fix("A-1", "satisfied"),
            fix("A-2", "not-satisfied", "satisfied"),
            fix("A-3", "not-satisfied", green=False),
        ))
        self.assertIn("Catches (own tests green, judge said no first): 1/2 (50%)", out)
        self.assertIn("Catches fixed in a later round: 1/1 (100%)", out)
        self.assertIn("1 round × 2, 2 rounds × 1", out)

    def test_inconclusive_rounds_are_skipped_for_the_first_verdict(self):
        out = judge_stats.summarize(log(fix("A-1", "inconclusive", "not-satisfied", "satisfied")))
        self.assertIn("judge said no first): 1/1", out)
        self.assertIn("Catches fixed in a later round: 1/1", out)

    def test_miss_needs_a_broken_retest_after_the_pass(self):
        out = judge_stats.summarize(log(fix("A-1", "satisfied"), fix("A-2", "satisfied"), retest("A-1", "broken")))
        self.assertIn("a later retest broke (miss): 1/2 (50%)", out)

    def test_broken_retest_before_the_fix_is_not_a_miss(self):
        out = judge_stats.summarize(log(retest("A-1", "broken"), fix("A-1", "satisfied")))
        self.assertIn("a later retest broke (miss): 0/1", out)

    def test_pr_rates_count_only_merged_or_closed(self):
        out = judge_stats.summarize(log(
            fix("A-1", "not-satisfied", "satisfied", prs=["u1"]),
            fix("A-2", "not-satisfied", "satisfied", prs=["u2"]),
            fix("A-3", "satisfied", prs=["u3"]),
        ), states({"u1": "MERGED", "u2": "OPEN", "u3": "CLOSED"}))
        self.assertIn("Catches confirmed by a merged PR: 1/1 (100%)", out)
        self.assertIn("PR closed unmerged (possible miss): 1/2 (50%)", out)
        self.assertIn("PRs merged or closed so far: 2/3", out)

    def test_all_lookups_failing_is_reported_not_zeroed(self):
        out = judge_stats.summarize(log(fix("A-1", "satisfied", prs=["u1"])), lambda url: (None, "gh auth login required"))
        self.assertIn("PR outcomes unavailable: gh auth login required", out)
        self.assertNotIn("confirmed by a merged PR", out)

    def test_each_pr_is_looked_up_once(self):
        calls = []
        def lookup(url):
            calls.append(url)
            return "MERGED", None
        judge_stats.summarize(log(fix("A-1", "satisfied", prs=["u1"]), fix("A-1", "satisfied", prs=["u1"])), lookup)
        self.assertEqual(calls, ["u1"])

    def test_any_merged_pr_counts_as_merged(self):
        self.assertEqual(judge_stats.outcome(["a", "b"], {"a": "CLOSED", "b": "MERGED"}), "MERGED")
        self.assertIsNone(judge_stats.outcome(["a"], {}))

    def test_retest_only_log_skips_the_fix_section(self):
        out = judge_stats.summarize(log(retest("A-1", "broken", judge="not-satisfied"), retest("A-2", "works")))
        self.assertNotIn("Rounds:", out)
        self.assertIn("Tests green but judge said no: 1/2 (50%)", out)

    def test_small_sample_warning(self):
        self.assertIn("too few to trust", judge_stats.summarize(log(fix("A-1", "satisfied"))))

    def test_malformed_records_are_skipped_not_fatal(self):
        result = run([
            "not json",
            {"kind": "retest", "verdict": "broken"},
            {"kind": "fix", "ticket": "A-9", "rounds": ["satisfied"]},
            {"kind": "fix", "ticket": "A-8", "rounds": "x"},
            fix("A-1", "satisfied"),
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Fix runs judged: 1", result.stdout)
        self.assertEqual(result.stderr.count("skipped"), 4)

    def test_cli_exits_2_when_empty_or_missing(self):
        self.assertEqual(run(["not json"]).returncode, 2)
        result = subprocess.run([sys.executable, SCRIPT, "/nonexistent/metrics.jsonl"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
