import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
import guard  # noqa: E402

DENIED = [
    "git push origin main",
    "git push origin master",
    "git push origin HEAD:main",
    "git push origin HEAD:refs/heads/main",
    "git push -u origin feature:master",
    "git push --force origin moth/X",
    "git push -f",
    "git push origin +moth/X",
    "git push --force-with-lease=moth/X origin moth/X",
    "cd repo && git push origin main",
    "git -C ../x push origin main",
    "gh pr merge 44",
    "cd repo && gh pr merge 44 --squash",
    "GH_TOKEN=x gh pr merge 44",
]

ALLOWED = [
    "git push -u origin moth/ACME-123 && gh pr create --draft --base main --body 'merge into main'",
    "git push",
    "git push -u origin moth/ACME-123",
    "git push origin main-fix",
    "git log main && echo push",
    "gh pr create --base main",
    "perl -pi -e 's/x/and gh pr merge/' README.md",
    "echo done; gh pr view 44",
    "python3 - <<'EOF'\ncases = ['git push --force origin x', 'git push origin main']\nEOF",
]


def is_denied(command):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            guard.check_bash(command, {})
    except SystemExit:
        return True
    return False


class GitPushRulesTest(unittest.TestCase):
    def test_denied(self):
        for command in DENIED:
            with self.subTest(command=command):
                self.assertTrue(is_denied(command))

    def test_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertFalse(is_denied(command))


if __name__ == "__main__":
    unittest.main()
