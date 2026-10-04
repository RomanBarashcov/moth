import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HOOKS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HOOKS)
import guard  # noqa: E402

DENIED = [
    "git push origin main",
    "git push origin master",
    "git push origin HEAD:main",
    "git push origin HEAD:refs/heads/main",
    "git push origin @:main",
    "git push -u origin feature:master",
    "git push --force origin moth/X",
    "git push -f",
    "git push -uf origin moth/X",
    "git push origin +moth/X",
    "git push --force-with-lease=moth/X origin moth/X",
    "git push --all origin",
    "git push --mirror origin",
    "cd repo && git push origin main",
    "git -C ../x push origin main",
    "git -c user.name=x push origin main",
    "git --git-dir=.git push origin main",
    "git --no-pager push origin main",
    "/usr/bin/git push origin main",
    "sudo git push origin main",
    "sudo -u bot git push origin main",
    "env GIT_TRACE=1 git push origin main",
    "command git push origin main",
    "nohup git push origin main",
    "bash -c 'git push origin main'",
    "sh -lc \"git push --force origin x\"",
    "eval 'git push origin main'",
    "(git push origin main)",
    "echo $(git push origin main)",
    "echo `git push origin main`",
    "true; git push origin main",
    "true;\ngit push origin main",
    "echo a &&\n  git push origin main",
    "echo a\n\ngit push origin main",
    "gh pr merge 44",
    "cd repo && gh pr merge 44 --squash",
    "GH_TOKEN=x gh pr merge 44",
    "gh -R owner/repo pr merge 44",
    "gh api -X PUT repos/o/r/pulls/44/merge",
]

ALLOWED = [
    "git push -u origin moth/ACME-123 && gh pr create --draft --base main --body 'merge into main'",
    "git push -u origin moth/ACME-123",
    "git push origin main-fix",
    "git push origin HEAD:moth/ACME-123",
    "git log main && echo push",
    "gh pr create --base main",
    "gh pr view 44",
    "perl -pi -e 's/x/and gh pr merge/' README.md",
    "echo 'cd repo && gh pr merge 44'",
    "echo done; gh pr view 44",
    "python3 - <<'EOF'\ncases = ['git push --force origin x', 'git push origin main']\nEOF",
    "git commit -m \"don't push to main\"",
    "git commit -q -F - <<'EOF'\nfix: a bare `git push` on main was allowed\n\ngit push origin main\nEOF",
    "cat > notes.md <<EOF\ngh pr merge 44\nEOF\ngit push -u origin moth/ACME-123",
]

HEREDOC_DENIED = [
    "bash <<'EOF'\ngit push origin main\nEOF",
    "sudo sh <<EOF\ngit push --force origin x\nEOF",
    "cat <<EOF\nnotes\nEOF\ngit push origin main",
    "cat <<EOF && git push origin main\nx\nEOF",
    "cat <<EOF; git push --force origin x\nx\nEOF",
]

UNVERIFIABLE_DENIED = [
    "git push origin $'main'",
    "B=main; git push origin $B",
    "git push origin {main,x}",
    "git push origin \"$(echo main)\"",
    "git push origin $(echo main)",
    "git push origin ma*",
    "git push origin \\\nmain",
]

ALIAS_DENIED = [
    "git p origin main",
    "git -c alias.q=push q origin main",
    "git -c 'alias.s=!git push origin main' s",
]


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(root, branch):
    path = os.path.join(root, branch.replace("/", "-"))
    os.makedirs(path)
    git("init", "-q", "-b", branch, cwd=path)
    git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init", cwd=path)
    return path


def is_denied(command, cwd=None):
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            guard.check_bash(command, {}, cwd)
    except SystemExit:
        return True
    return False


class GitPushRulesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.feature_repo = make_repo(cls.tmp.name, "moth/ACME-123")
        git("config", "alias.p", "push", cwd=cls.feature_repo)
        cls.main_repo = make_repo(cls.tmp.name, "main")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_denied(self):
        for command in DENIED:
            with self.subTest(command=command):
                self.assertTrue(is_denied(command, self.feature_repo))

    def test_unverifiable_targets_and_aliases_are_denied(self):
        for command in UNVERIFIABLE_DENIED + ALIAS_DENIED:
            with self.subTest(command=command):
                self.assertTrue(is_denied(command, self.feature_repo))
        self.assertFalse(is_denied("git p origin moth/ACME-123", self.feature_repo))

    def test_heredoc_body_is_checked_only_when_a_shell_runs_it(self):
        for command in HEREDOC_DENIED:
            with self.subTest(command=command):
                self.assertTrue(is_denied(command, self.feature_repo))
        commit_message = "git commit -F - <<'EOF'\na bare `git push` on main\ngit push\nEOF"
        self.assertFalse(is_denied(commit_message, self.main_repo))

    def test_allowed(self):
        for command in ALLOWED:
            with self.subTest(command=command):
                self.assertFalse(is_denied(command, self.feature_repo))

    def test_bare_push_uses_current_branch(self):
        for command in ("git push", "git push origin", "git push origin HEAD", "git push -u origin @"):
            with self.subTest(command=command):
                self.assertFalse(is_denied(command, self.feature_repo))
                self.assertTrue(is_denied(command, self.main_repo))

    def test_cd_changes_the_branch_that_is_checked(self):
        self.assertFalse(is_denied(f"cd {self.feature_repo} && git push", self.main_repo))
        self.assertTrue(is_denied(f"cd {self.main_repo} && git push", self.feature_repo))
        self.assertTrue(is_denied(f"git -C {self.main_repo} push", self.feature_repo))


class FailClosedTest(unittest.TestCase):
    def run_hook(self, guard_json, command="echo hi", stdin=None):
        with tempfile.TemporaryDirectory() as project:
            if guard_json is not None:
                os.makedirs(os.path.join(project, ".moth"))
                with open(os.path.join(project, ".moth", "guard.json"), "w") as f:
                    f.write(guard_json)
            payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": project}
            result = subprocess.run(
                [sys.executable, os.path.join(HOOKS, "guard.py")],
                input=json.dumps(payload) if stdin is None else stdin, capture_output=True, text=True,
                env={**os.environ, "CLAUDE_PROJECT_DIR": project},
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_malformed_guard_json_denies(self):
        self.assertIn('"deny"', self.run_hook("{not json"))

    def test_invalid_rule_denies(self):
        self.assertIn('"deny"', self.run_hook('{"bash_deny": [{"pattern": "("}]}'))

    def test_unreadable_payload_denies(self):
        self.assertIn('"deny"', self.run_hook("{}", stdin="not json"))

    def test_valid_guard_allows_harmless_command(self):
        self.assertEqual(self.run_hook('{"bash_deny": []}'), "")

    def test_no_workspace_is_inactive(self):
        self.assertEqual(self.run_hook(None, "git push origin main"), "")


if __name__ == "__main__":
    unittest.main()
