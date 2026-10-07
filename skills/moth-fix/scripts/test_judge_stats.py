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


def run(lines, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write("\n".join(l if isinstance(l, str) else json.dumps(l) for l in lines))
    try:
        return subprocess.run([sys.executable, SCRIPT, f.name, *args], capture_output=True, text=True)
    finally:
        os.unlink(f.name)


class JudgeStatsTest(unittest.TestCase):
    def test_catch_counts_only_green_runs_rejected_in_round_one(self):
        out = judge_stats.summarize([
            fix("A-1", "satisfied"),
            fix("A-2", "not-satisfied", "satisfied"),
            fix("A-3", "not-satisfied", green=False),
        ])
        self.assertIn("Catches (own tests green, judge said no in round 1): 1/2 (50%)", out)
        self.assertIn("Catches fixed in a later round: 1/1 (100%)", out)
        self.assertIn("1 round × 2, 2 rounds × 1", out)

    def test_miss_is_a_pass_followed_by_a_broken_retest(self):
        out = judge_stats.summarize([fix("A-1", "satisfied"), fix("A-2", "satisfied"), retest("A-1", "broken")])
        self.assertIn("Judge passed, retest later broken (miss): 1/2 (50%)", out)

    def test_pr_outcomes_with_lookup(self):
        states = {"u1": "MERGED", "u2": "CLOSED", "u3": "OPEN"}
        out = judge_stats.summarize([
            fix("A-1", "not-satisfied", "satisfied", prs=["u1"]),
            fix("A-2", "satisfied", prs=["u2"]),
            fix("A-3", "satisfied", prs=["u3"]),
        ], states.get)
        self.assertIn("Catches confirmed by a merged PR: 1/1 (100%)", out)
        self.assertIn("Judge passed, PR closed unmerged (possible miss): 1/3 (33%)", out)
        self.assertIn("PRs with a final state: 2/3", out)

    def test_any_merged_pr_counts_as_merged(self):
        self.assertEqual(judge_stats.outcome(["a", "b"], {"a": "CLOSED", "b": "MERGED"}.get), "MERGED")
        self.assertIsNone(judge_stats.outcome(["a"], lambda url: None))

    def test_retest_catch(self):
        out = judge_stats.summarize([retest("A-1", "broken", judge="not-satisfied"), retest("A-2", "works")])
        self.assertIn("Tests green but judge said no: 1/2 (50%)", out)

    def test_small_sample_warning(self):
        self.assertIn("too few to trust", judge_stats.summarize([fix("A-1", "satisfied")]))

    def test_cli_skips_bad_lines_and_exits_2_when_empty(self):
        result = run(["not json", fix("A-1", "satisfied"), {"kind": "other"}])
        self.assertEqual(result.returncode, 0)
        self.assertIn("Fix runs judged: 1", result.stdout)
        self.assertIn("line 1 is not JSON", result.stderr)
        self.assertEqual(run(["not json"]).returncode, 2)

    def test_missing_file_exits_2(self):
        result = subprocess.run([sys.executable, SCRIPT, "/nonexistent/metrics.jsonl"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
