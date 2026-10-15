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

EXPANDED_OR_CASED_DENIED = [
    "X=push; git $X origin main",
    "git \"$(echo push)\" origin main",
    "g=git; $g push origin main",
    "\"$GIT\" push origin main",
    "GIT push origin main",
    "Git push origin main",
    "BASH -c \"git push origin main\"",
    "SUDO git push origin main",
    "GH pr merge 1",
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
        for command in UNVERIFIABLE_DENIED + ALIAS_DENIED + EXPANDED_OR_CASED_DENIED:
            with self.subTest(command=command):
                self.assertTrue(is_denied(command, self.feature_repo))
        self.assertFalse(is_denied("git p origin moth/ACME-123", self.feature_repo))
        self.assertFalse(is_denied("$EDITOR notes.md", self.feature_repo))

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


class FindGuardTest(unittest.TestCase):
    def test_found_in_parent_up_to_git_top_level(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".git"))
            os.makedirs(os.path.join(root, ".moth"))
            path = os.path.join(root, ".moth", "guard.json")
            with open(path, "w") as f:
                f.write("{}")
            sub = os.path.join(root, "apps", "web")
            os.makedirs(sub)
            self.assertEqual(guard.find_guard(sub), path)

    def test_stops_at_git_top_level(self):
        with tempfile.TemporaryDirectory() as outer:
            os.makedirs(os.path.join(outer, ".moth"))
            with open(os.path.join(outer, ".moth", "guard.json"), "w") as f:
                f.write("{}")
            repo = os.path.join(outer, "repo")
            os.makedirs(os.path.join(repo, ".git"))
            self.assertIsNone(guard.find_guard(repo))


if __name__ == "__main__":
    unittest.main()


class HoldoutTest(unittest.TestCase):
    """The fixer (main thread or any other agent) must not read .moth/scenarios/."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.project = cls.tmp.name
        git("init", "-q", cwd=cls.project)
        os.makedirs(os.path.join(cls.project, ".moth", "scenarios", "ACME-1"))
        os.makedirs(os.path.join(cls.project, ".moth", "knowledge"))
        os.makedirs(os.path.join(cls.project, "src"))
        with open(os.path.join(cls.project, ".moth", "guard.json"), "w") as f:
            f.write("{}")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_hook(self, tool_name, tool_input, agent_type=None):
        payload = {"tool_name": tool_name, "tool_input": tool_input, "cwd": self.project}
        if agent_type:
            payload["agent_type"] = agent_type
        result = subprocess.run(
            [sys.executable, os.path.join(HOOKS, "guard.py")],
            input=json.dumps(payload), capture_output=True, text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": self.project},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return '"deny"' in result.stdout

    def scenario(self):
        return os.path.join(self.project, ".moth", "scenarios", "ACME-1", "scenarios.md")

    def test_fixer_is_denied(self):
        denied = [
            ("Read", {"file_path": self.scenario()}),
            ("Read", {"file_path": ".moth/scenarios/ACME-1/scenarios.md"}),
            ("Edit", {"file_path": self.scenario(), "old_string": "a", "new_string": "b"}),
            ("Grep", {"pattern": "ACME", "path": ".moth/scenarios"}),
            ("Grep", {"pattern": "ACME", "path": ".moth"}),
            ("Grep", {"pattern": "Then", "glob": ".moth/**/*.md"}),
            ("Glob", {"pattern": ".moth/scenarios/**"}),
            ("Bash", {"command": "cat .moth/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat .moth/sc*/*/*.md"}),
            ("Bash", {"command": "ls .moth"}),
            ("Bash", {"command": "grep -rn ACME ."}),
            ("Bash", {"command": "grep -R Then"}),
            ("Bash", {"command": "find . -name '*.md'"}),
            ("Bash", {"command": "rg --hidden --no-ignore ACME"}),
            ("Bash", {"command": "cd src && grep -r ACME .."}),
            ("Bash", {"command": "cat .moth/knowledge/../scenarios/ACME-1/scenarios.md"}),
            ("Read", {"file_path": ".moth/knowledge/../scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat .MOTH/Scenarios/ACME-1/scenarios.md"}),
            ("Read", {"file_path": ".MOTH/Scenarios/ACME-1/scenarios.md"}),
            ("Grep", {"pattern": "x", "path": ".Moth/SCENARIOS"}),
            ("Bash", {"command": "git grep --no-index Then"}),
            ("Bash", {"command": "rgrep Then"}),
            ("Bash", {"command": "cat .mo''th/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat .mo\\th/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat \".mo\"th/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "sh -c 'cat .mo\"\"th/scen*/*/*'"}),
            ("Bash", {"command": "cat .mo*/sc*/*/*"}),
            ("Bash", {"command": "cat .{moth,x}/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat {.moth,x}/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat " + "{a,b}" * 8 + ".{moth,x}/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat .@(moth)/scenarios/ACME-1/scenarios.md"}),
            ("Glob", {"pattern": ".+(moth)/**"}),
            ("Bash", {"command": "cat .mo''th/scenarios/ACME-1/scenarios.md '"}),
            ("Bash", {"command": "cat .mot?/scenarios/ACME-1/scenarios.md"}),
            ("Bash", {"command": "cat $'\\x2emoth/scenarios/ACME-1/scenarios.md'"}),
            ("Glob", {"pattern": ".m*/**/*.md"}),
            ("Grep", {"pattern": "Then", "glob": ".*/scenarios/**"}),
        ]
        for tool, tool_input in denied:
            with self.subTest(tool=tool, tool_input=tool_input):
                self.assertTrue(self.run_hook(tool, tool_input))
                for impostor in ("general-purpose", "moth-verifier", "other:moth-verifier", "moth:other"):
                    self.assertTrue(self.run_hook(tool, tool_input, agent_type=impostor))

    def test_fixer_keeps_normal_access(self):
        allowed = [
            ("Read", {"file_path": ".moth/system.yaml"}),
            ("Read", {"file_path": os.path.join(self.project, ".moth", "knowledge", "INDEX.md")}),
            ("Read", {"file_path": "src/app.go"}),
            ("Grep", {"pattern": "ACME", "path": "src"}),
            ("Grep", {"pattern": "ACME"}),
            ("Glob", {"pattern": "src/**/*.go"}),
            ("Bash", {"command": "cat .moth/system.yaml"}),
            ("Bash", {"command": "echo '{}' >> .moth/metrics.jsonl"}),
            ("Write", {"file_path": ".moth/metrics.jsonl", "content": "{}"}),
            ("Bash", {"command": "grep -rn ACME src"}),
            ("Bash", {"command": "find src -name '*.go'"}),
            ("Bash", {"command": "rg ACME"}),
            ("Bash", {"command": "grep -n ACME README.md"}),
            ("Bash", {"command": "ls src/*.go"}),
            ("Glob", {"pattern": "**/*.go"}),
            ("Bash", {"command": "cp src/{a,b}.go /tmp"}),
        ]
        for tool, tool_input in allowed:
            with self.subTest(tool=tool, tool_input=tool_input):
                self.assertFalse(self.run_hook(tool, tool_input))

    def test_scenario_writer_and_verifier_may_read(self):
        for agent in ("moth:moth-scenario-writer", "moth:moth-verifier"):
            with self.subTest(agent=agent):
                self.assertFalse(self.run_hook("Read", {"file_path": self.scenario()}, agent))
                self.assertFalse(self.run_hook("Write", {"file_path": self.scenario(), "content": "x"}, agent))
                self.assertFalse(self.run_hook("Bash", {"command": "cat .moth/scenarios/ACME-1/scenarios.md"}, agent))
