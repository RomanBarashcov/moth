import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "satisfaction.py")


def result(status, message=None):
    r = {"status": status, "retry": 0}
    if message:
        r["error"] = {"message": message}
    return r


def spec(title, *statuses, project="chromium"):
    return {"title": title, "tests": [{"projectName": project, "results": [result(s, "boom\nstack") for s in statuses]}]}


def report(*specs, suites=None):
    return {"suites": [{"title": "bugs/ACME-1.spec.ts", "specs": list(specs), "suites": suites or []}]}


def run(data, *args):
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        f.write(data if isinstance(data, str) else json.dumps(data))
    try:
        return subprocess.run([sys.executable, SCRIPT, f.name, *args], capture_output=True, text=True)
    finally:
        os.unlink(f.name)


class SatisfactionTest(unittest.TestCase):
    def test_all_pass(self):
        r = run(report(
            spec("S1 [v1] login with new password", "passed", "passed", "passed"),
            spec("S1 [v2] login with new password", "passed", "passed", "passed"),
        ))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("**Satisfaction: 1.00 (6/6)** — min 0.90 ✅", r.stdout)
        self.assertIn("| S1 login with new password | 6/6 | v1 3/3 · v2 3/3 | no |", r.stdout)
        self.assertNotIn("Failing", r.stdout)

    def test_one_variation_failing(self):
        r = run(report(
            spec("S1 [v1] reset", "passed", "passed", "passed"),
            spec("S1 [v2] reset", "failed", "failed", "failed"),
        ))
        self.assertEqual(r.returncode, 1)
        self.assertIn("(3/6)** — min 0.90 ❌", r.stdout)
        self.assertIn("v1 3/3 · v2 0/3 | no |", r.stdout)
        self.assertIn("- S1 [v2] reset (chromium): boom", r.stdout)

    def test_flaky(self):
        r = run(report(
            spec("S1 [v1] reset", "passed", "failed", "passed"),
            spec("S1 [v2] reset", "passed", "passed", "passed"),
        ), "--min", "0.5")
        self.assertEqual(r.returncode, 0)
        self.assertIn("| S1 reset | 5/6 | v1 2/3 · v2 3/3 | yes |", r.stdout)

    def test_nested_suites_and_two_projects(self):
        inner = {"title": "describe", "specs": [], "suites": [{"title": "deeper", "specs": [{
            "title": "S2 [v1] checkout",
            "tests": [
                {"projectName": "chromium", "results": [result("passed"), result("passed")]},
                {"projectName": "firefox", "results": [result("timedOut", "Timeout 30000ms"), result("passed")]},
            ],
        }]}]}
        r = run(report(spec("S1 [v1] login", "passed"), suites=[inner]), "--min", "0.5")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("(4/5)", r.stdout)
        self.assertIn("| S2 checkout | 3/4 | v1 3/4 | yes |", r.stdout)
        self.assertIn("- S2 [v1] checkout (firefox): Timeout 30000ms", r.stdout)

    def test_browser_specific_failure_is_not_flaky(self):
        s = {"title": "S1 [v1] login", "tests": [
            {"projectName": "chromium", "results": [result("passed"), result("passed")]},
            {"projectName": "firefox", "results": [result("failed", "x"), result("failed", "x")]},
        ]}
        r = run(report(s), "--min", "0.5")
        self.assertIn("| S1 login | 2/4 | v1 2/4 | no |", r.stdout)

    def test_score_floored_exactly(self):
        r = run(report(spec("S1 [v1] x", *["passed"] * 29, *["failed"] * 21)), "--min", "0.5")
        self.assertIn("**Satisfaction: 0.58 (29/50)**", r.stdout)

    def test_skipped_excluded(self):
        r = run(report(spec("S1 [v1] login", "passed", "skipped", "passed")))
        self.assertEqual(r.returncode, 0)
        self.assertIn("(2/2)", r.stdout)

    def test_bad_title_goes_to_other(self):
        r = run(report(spec("S1 [v1] login", "passed"), spec("login works", "passed")))
        self.assertEqual(r.returncode, 0)
        self.assertIn("| other | 1/1 |", r.stdout)
        self.assertIn("login works", r.stderr)

    def test_scenario_below_min_fails_despite_overall(self):
        good = [spec(f"S1 [v{k}] login", *["passed"] * 10) for k in range(1, 4)]
        r = run(report(*good, spec("S2 [v1] logout", "passed", "failed")))
        self.assertIn("(31/32)", r.stdout)
        self.assertEqual(r.returncode, 1)
        self.assertIn("❌", r.stdout)
        self.assertIn("Below min: S2 (0.50)", r.stdout)

    def test_long_error_truncated_and_capped(self):
        r = run(report(spec("S1 [v1] x", *["failed"] * 7)))
        s = report(spec("S1 [v1] x", "failed"))
        s["suites"][0]["specs"][0]["tests"][0]["results"][0]["error"]["message"] = "\x1b[31m" + "e" * 300
        long = run(s)
        line = [l for l in long.stdout.splitlines() if l.startswith("- S1")][0]
        self.assertLessEqual(len(line.split(": ", 1)[1]), 120)
        self.assertEqual(sum(l.startswith("- S1") for l in r.stdout.splitlines()), 5)
        self.assertIn("- … and 2 more", r.stdout)

    def test_empty_report(self):
        self.assertEqual(run({"suites": []}).returncode, 2)
        self.assertEqual(run(report(spec("S1 [v1] x", "skipped"))).returncode, 2)

    def test_unreadable(self):
        self.assertEqual(run("not json").returncode, 2)
        r = subprocess.run([sys.executable, SCRIPT, "/nonexistent.json"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
