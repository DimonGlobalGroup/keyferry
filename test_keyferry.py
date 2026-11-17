#!/usr/bin/env python3
"""Tests for KeyFerry. Stdlib unittest only."""

import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(HERE, "keyferry.py")
CANARY = "CANARY-VALUE-9f3e7d-never-print-me"


def run(*argv, cwd=HERE):
    return subprocess.run(
        [sys.executable, TOOL, *argv],
        capture_output=True, text=True, cwd=cwd)


class KeyFerryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_clean_audit_exit_0(self):
        p = self.write("a.env", "ALPHA=1\nBETA=two\nGAMMA=3\n")
        r = run("audit", p)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 keys", r.stdout)
        self.assertIn("0 errors, 0 warnings", r.stdout)

    def test_values_never_printed_canary(self):
        p = self.write("a.env", f"ALPHA={CANARY}\nbeta={CANARY}\nBAD LINE\n")
        for extra in ([], ["--json"]):
            r = run("audit", *extra, p)
            self.assertNotIn(CANARY, r.stdout)
            self.assertNotIn(CANARY, r.stderr)
            self.assertNotIn("9f3e7d", r.stdout)

    def test_duplicate_key_error_with_lines(self):
        p = self.write("a.env", "ALPHA=1\nBETA=2\nALPHA=3\n")
        r = run("audit", p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("duplicate-key ALPHA line 3 first line 1", r.stdout)

    def test_malformed_lines(self):
        p = self.write("a.env", "NO EQUALS HERE\n9BAD=1\nGOOD=1\n")
        r = run("audit", p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("malformed-line line 1", r.stdout)
        self.assertIn("malformed-line line 2", r.stdout)

    def test_empty_and_nonstandard_are_warnings(self):
        p = self.write("a.env", "ALPHA=\nlower_case=1\n")
        r = run("audit", p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("empty-value ALPHA", r.stdout)
        self.assertIn("nonstandard-key lower_case", r.stdout)
        self.assertIn("0 errors, 2 warnings", r.stdout)

    def test_unsorted_warning_once(self):
        p = self.write("a.env", "BETA=1\nALPHA=2\nGAMMA=3\nDELTA=4\n")
        r = run("audit", p)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.count("unsorted-keys"), 1)
        self.assertIn("unsorted-keys ALPHA line 2 after BETA", r.stdout)

    def test_export_prefix_and_comments(self):
        p = self.write("a.env", "# comment\n\nexport ALPHA=1\nBETA=x=y\n")
        r = run("audit", p)
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("2 keys", r.stdout)

    def test_check_missing_and_extra(self):
        t = self.write("tpl.env", "ALPHA=fill\nBETA=fill\nGAMMA=fill\n")
        p = self.write("a.env", "ALPHA=1\nBETA=2\nEXTRA=9\n")
        r = run("check", "--template", t, p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("missing-key GAMMA", r.stdout)
        self.assertIn("extra-key EXTRA", r.stdout)

    def test_check_empty_template_value_is_error(self):
        t = self.write("tpl.env", "ALPHA=fill\nBETA=fill\n")
        p = self.write("a.env", "ALPHA=1\nBETA=\n")
        r = run("check", "--template", t, p)
        self.assertEqual(r.returncode, 1)
        self.assertIn("empty-value BETA", r.stdout)
        self.assertIn("1 errors", r.stdout)

    def test_check_parity_ok(self):
        t = self.write("tpl.env", "ALPHA=fill\nBETA=fill\n")
        p = self.write("a.env", "BETA=2\nALPHA=1\n")
        r = run("check", "--template", t, p)
        # Unsorted is only a warning; parity itself is clean.
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_missing_file_exit_2_no_traceback(self):
        r = run("audit", os.path.join(self.dir, "nope.env"))
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("Traceback", r.stderr)

    def test_no_command_exit_2(self):
        r = run()
        self.assertEqual(r.returncode, 2)

    def test_json_shape_and_determinism(self):
        p = self.write("a.env", "ALPHA=1\nALPHA=2\n")
        r1 = run("audit", "--json", p)
        r2 = run("audit", "--json", p)
        self.assertEqual(r1.stdout, r2.stdout)
        data = json.loads(r1.stdout)
        self.assertEqual(data["files"][0]["counts"]["duplicate-key"], 1)
        self.assertIn("summary", data)

    def test_max_examples_cap_counts_suppressed(self):
        body = "".join(f"K{i:02d}=\n" for i in range(5))
        p = self.write("a.env", body)
        r = run("audit", "--max-examples", "2", p)
        self.assertIn("empty-value = 5", r.stdout.replace("empty-value K", "empty-value K")) \
            if False else self.assertIn("and 3 more", r.stdout)
        self.assertIn("0 errors, 5 warnings", r.stdout)

    def test_read_only(self):
        p = self.write("a.env", "ALPHA=1\n")
        before = sorted(os.listdir(self.dir))
        run("audit", p)
        self.assertEqual(sorted(os.listdir(self.dir)), before)

    def test_version(self):
        r = run("--version")
        self.assertEqual(r.returncode, 0)
        self.assertIn("1.0.0", r.stdout)


if __name__ == "__main__":
    unittest.main()
