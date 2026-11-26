import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vortex.design import audit, preview
from vortex.engineering import inspect_project, rebuild
from vortex.methods_cli import add_commands
from vortex.research import synthesize


def design_tokens():
    return {
        "name": "Palette",
        "colors": {"canvas": "#fff", "ink": "#000", "muted": "#777", "soft": "#ccc"},
        "spacing": {"small": 8, "medium": 16},
        "typography": {"display": {"size_px": 24, "weight": 400}},
        "contrast_pairs": [
            {"foreground": "ink", "background": "canvas"},
            {"foreground": "muted", "background": "canvas"},
            {"foreground": "muted", "background": "canvas", "typography": "display"},
        ],
    }


def review_claim(identifier, source, quote, **options):
    return {"id": identifier, "statement": f"Claim for {identifier}",
            "evidence": [{"source": source, "quote": quote, **options}]}


def reconstruction(sources, *capabilities):
    return {"question": "What can be checked in the new implementation?",
            "sources": sources, "capabilities": list(capabilities)}


class TestDesign(unittest.TestCase):
    def test_contrast_threshold_depends_on_text_size(self):
        result = audit(design_tokens())
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["colors"]["canvas"], "#ffffff")
        self.assertEqual(result["contrast"][0]["ratio"], 21.0)
        self.assertEqual([row["passes"] for row in result["contrast"]], [True, False, True])
        self.assertEqual([row["minimum"] for row in result["contrast"]], [4.5, 4.5, 3.0])

    def test_audit_handles_bold_large_text_and_empty_pairs(self):
        spec = design_tokens()
        spec["typography"]["bold"] = {"size_px": 19, "weight": 700}
        spec["contrast_pairs"][1]["typography"] = "bold"
        self.assertEqual(audit(spec)["status"], "PASS")
        spec["contrast_pairs"] = []
        self.assertEqual(audit(spec)["status"], "UNVERIFIED")

    def test_reject_css_and_invalid_tokens(self):
        tokens = design_tokens()
        tokens["colors"]["ink"] = "red; background:url(x)"
        with self.assertRaises(ValueError):
            audit(tokens)
        tokens = design_tokens()
        tokens["spacing"]["small"] = True
        with self.assertRaises(ValueError):
            audit(tokens)
        tokens = design_tokens()
        tokens["contrast_pairs"][0]["foreground"] = "missing"
        with self.assertRaises(ValueError):
            audit(tokens)

    def test_preview_escapes_name_and_protects_existing_destination(self):
        tokens = design_tokens()
        tokens["name"] = "<script>preview()</script>"
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / "tokens.html"
            result = preview(tokens, output)
            body = output.read_text(encoding="utf-8")
            self.assertIn("&lt;script&gt;preview()&lt;/script&gt;", body)
            self.assertNotIn("<script>", body)
            self.assertIn("Content-Security-Policy", body)
            self.assertIn("Needs review", body)
            self.assertEqual(result["output"], str(output))
            with self.assertRaises(FileExistsError):
                preview(tokens, output)
            self.assertEqual(output.read_text(encoding="utf-8"), body)


class TestResearch(unittest.TestCase):
    def test_exact_excerpts_deduplicate_sources_and_surface_conflicts(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            document = b"Heading\r\nFirst observation\r\nwith two lines.\r\n"
            (root / "report.txt").write_bytes(document)
            (root / "copy.txt").write_bytes(document)
            (root / "second.txt").write_text("Counterexample.", encoding="utf-8")
            repeated = review_claim("mixed", "first", "First observation\nwith two lines.")
            repeated["evidence"].extend([
                {"source": "copy", "quote": "First observation", "stance": "supports"},
                {"source": "second", "quote": "Counterexample.", "stance": "challenges"},
            ])
            result = synthesize({
                "question": "Does the evidence agree?",
                "sources": {"first": {"path": "report.txt"}, "copy": {"path": "copy.txt"},
                            "second": {"path": "second.txt", "origin": "Local notes"}},
                "claims": [repeated, review_claim("missing", "first", "Made up evidence.")],
            }, root)
            mixed, missing = result["claims"]
            self.assertEqual(mixed["status"], "MIXED_EXCERPTS")
            self.assertEqual(mixed["supporting_sources"], ["first"])
            self.assertEqual(mixed["challenging_sources"], ["second"])
            self.assertEqual(mixed["evidence"][0]["line_start"], 2)
            self.assertEqual(mixed["evidence"][0]["line_end"], 3)
            self.assertEqual(result["sources"][1]["canonical_id"], "first")
            self.assertEqual(result["sources"][0]["sha256"], hashlib.sha256(document).hexdigest())
            self.assertEqual(missing["status"], "INSUFFICIENT_EVIDENCE")
            self.assertEqual(result["coverage"]["claims_with_support"], 1)
            self.assertEqual(result["coverage"]["unverified_excerpts"], 1)
            self.assertEqual(result["coverage"]["unresolved"], 2)

    def test_source_root_boundary(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            sub = root / "source"
            sub.mkdir()
            outside = root / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            linked = sub / "linked.txt"
            linked.symlink_to(outside)
            for path in ("../outside.txt", str(outside), "linked.txt"):
                with self.subTest(path=path), self.assertRaises(ValueError):
                    synthesize({"question": "Question?", "sources": {"x": {"path": path}},
                                "claims": [review_claim("x", "x", "outside")]}, sub)


class TestEngineering(unittest.TestCase):
    def test_inventory_compiles_without_running_imports_or_code(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "src").mkdir()
            marker = root / "marker"
            (root / "src" / "tool.py").write_text(
                f"import os\nfrom missing_package import dependency\n"
                f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
                f"class Formatter:\n    def apply(self):\n        return 1\n",
                encoding="utf-8",
            )
            (root / "src" / "consumer.py").write_text("from tool import Formatter\n", encoding="utf-8")
            (root / "ignored.py").symlink_to(root / "src" / "tool.py")
            (root / "pyproject.toml").write_text(
                '[project]\nname = "fixture"\nrequires-python = ">=3.15.2"\n'
                'dependencies = ["missing-package>=1"]\n', encoding="utf-8",
            )
            with self.assertRaises(FileNotFoundError):
                inspect_project(root / "missing")
            result = inspect_project(root)
            self.assertFalse(marker.exists())
            self.assertEqual(result["status"], "INSPECTED")
            self.assertEqual(result["compiled_sources"], 2)
            self.assertEqual(result["package"]["dependencies"], ["missing-package>=1"])
            by_path = {row["path"]: row for row in result["files"]}
            self.assertNotIn("ignored.py", by_path)
            self.assertEqual(by_path["src/tool.py"]["symbols"], ["Formatter", "Formatter.apply"])
            self.assertEqual(by_path["src/consumer.py"]["imports"][0]["category"], "project")
            self.assertEqual([row["category"] for row in by_path["src/tool.py"]["imports"]],
                             ["stdlib", "external_or_unresolved", "stdlib"])

    def test_syntax_and_manifest_errors_are_attributed(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "invalid.py").write_text("return\n", encoding="utf-8")
            (root / "pyproject.toml").write_text('[project]\nname = 1979-05-27\n', encoding="utf-8")
            result = inspect_project(root)
            self.assertEqual(result["status"], "REVIEW_REQUIRED")
            self.assertEqual({row["path"] for row in result["errors"]},
                             {"invalid.py", "pyproject.toml"})
            json.dumps(result)

    def test_study_build_check_and_exact_source_overlap(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            candidate.mkdir()
            code = "def format_name(text):\n    return text.strip()\n"
            (candidate / "formatter.py").write_text(code, encoding="utf-8")
            (root / "requirements.md").write_text("Strip whitespace from names.\n", encoding="utf-8")
            capability = review_claim("format", "requirements", "Strip whitespace from names.")
            capability["checks"] = [{"path": "formatter.py", "symbols": ["format_name"]}]
            spec = reconstruction({"requirements": {"path": "requirements.md"}}, capability)
            result = rebuild(spec, candidate, source_root=root)
            self.assertEqual(result["status"], "READY_FOR_RUNTIME_TEST")
            self.assertEqual(result["check"]["capabilities"][0]["status"], "STATIC_MATCH")
            self.assertFalse(result["check"]["reference_source_reviewed"])
            self.assertEqual(result["build"]["compiled_sources"], 1)
            reference = root / "reference"
            reference.mkdir()
            (reference / "previous.py").write_text(code, encoding="utf-8")
            checked = rebuild(spec, candidate, source_root=root, reference_source=reference)
            self.assertEqual(checked["status"], "REVIEW_REQUIRED")
            self.assertEqual(checked["check"]["exact_source_matches"][0]["reference"], ["previous.py"])

    def test_supplemental_evidence_cannot_replace_primary_or_checks(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            candidate = root / "candidate"
            candidate.mkdir()
            (candidate / "formatter.py").write_text("def other():\n    return None\n", encoding="utf-8")
            (root / "notes.txt").write_text("A formatting interface is expected.", encoding="utf-8")
            missing = {"id": "format", "statement": "Provide formatting",
                       "checks": [{"path": "formatter.py", "symbols": ["format_name"]}]}
            extra = review_claim("format", "notes", "A formatting interface is expected.")
            unused = review_claim("unrelated", "missing", "Unrelated excerpt.")
            supplement = {"question": "Which facts are absent in Study?",
                          "sources": {"notes": {"path": "notes.txt"}, "missing": {"path": "absent.txt"}},
                          "claims": [extra, unused]}
            result = rebuild(reconstruction({}, missing), candidate, source_root=root,
                             supplemental=(supplement, root))
            self.assertEqual(result["status"], "REVIEW_REQUIRED")
            self.assertEqual(result["study"]["claims"][0]["status"], "INSUFFICIENT_EVIDENCE")
            self.assertEqual(result["study"]["supplemental"]["claims"][0]["status"],
                             "SUPPORTING_EXCERPTS")
            check = result["check"]["capabilities"][0]
            self.assertEqual(check["checks"][0]["missing_symbols"], ["format_name"])


class TestMethodsCLI(unittest.TestCase):
    def test_commands_dispatch(self):
        parser = argparse.ArgumentParser()
        add_commands(parser.add_subparsers(required=True))
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            spec = root / "tokens.json"
            spec.write_text(json.dumps(design_tokens()), encoding="utf-8")
            args = parser.parse_args(["design", "audit", str(spec)])
            self.assertEqual(args.technical_handler(args)["status"], "REVIEW_REQUIRED")
            args = parser.parse_args(["engineering", "inspect", str(root)])
            self.assertEqual(args.technical_handler(args)["status"], "INSPECTED")
