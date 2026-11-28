import base64
from hashlib import sha256
from html.parser import HTMLParser
import math
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import unittest

from vortex.conversation import Conversation
from vortex.discipline import prepare_task
from vortex.interface import contrast_report, render_gallery, render_menu, write_preview
from vortex.motion import Motion, PRESETS


class MotionUITests(unittest.TestCase):
    def test_spring_endpoints_finite_and_volume(self):
        for motion in PRESETS.values():
            self.assertEqual(motion.frame(1), (1.0, 1.0, 0.0))
            for i in range(101):
                x, y, travel = motion.frame(i / 100)
                self.assertTrue(all(map(math.isfinite, (x, y, travel))))
                self.assertAlmostEqual(x * y, 1)
                self.assertLessEqual(abs(travel), 24)
            with self.assertRaises(ValueError):
                motion.frame(float("nan"))
        with self.assertRaises(ValueError):
            Motion(0, 390, 19, .1, 0, "ring")
        with self.assertRaises(ValueError):
            PRESETS["impact"].keyframes("invalid}")

    def test_menu_uses_real_conversation_and_does_not_activate_host(self):
        session = Conversation(locale="pt", enabled={"design", "android"})
        html = render_menu(session=session)
        self.assertIn('id="section-functions"', html)
        self.assertIn("Android e APK", html)
        self.assertNotIn("Geoinformação", html)
        self.assertIn("motion designer", html)
        self.assertEqual(session.handle("menu")["kind"], "pass_through")
        self.assertIn("No bound tools.", render_menu(locale="en"))
        self.assertIn("entrega não autorizada", html)

    def test_csp_exact_hash_native_controls_and_reduced_motion(self):
        for html in (render_menu(), render_gallery(), render_gallery(still=True)):
            style = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
            digest = base64.b64encode(sha256(style.encode()).digest()).decode()
            self.assertIn("style-src 'sha256-" + digest + "'", html)
            self.assertIn("script-src 'none'", html)
            self.assertIn("prefers-reduced-motion:reduce", html)
            self.assertNotIn("<script", html)
            self.assertNotIn("<form", html)
        gallery = render_gallery(still=True)
        for tag in ('type="checkbox"', 'type="radio"', 'type="range"', 'type="text"', "<progress", "<details"):
            self.assertIn(tag, gallery)
        self.assertIn('class="still"', gallery)

    def test_contrast_and_private_preview_fail_closed(self):
        self.assertEqual(contrast_report()["status"], "PASS")
        with TemporaryDirectory() as directory:
            output = Path(directory) / "candidate"
            result = write_preview(output)
            self.assertEqual(result["status"], "REVIEW_REQUIRED")
            self.assertFalse(result["delivery_authorized"])
            self.assertEqual(result["security"]["findings"], [])
            self.assertEqual(result["bytes"], (output / "index.html").stat().st_size)
            with self.assertRaises(FileExistsError):
                write_preview(output)
            self.assertFalse((Path(directory) / "invalid").exists())
            with self.assertRaises(ValueError):
                write_preview(Path(directory) / "invalid", locale="bad")

    def test_motion_profiles_only_when_design_allowed(self):
        roles = lambda task, **kw: {p["role"] for p in prepare_task(task, **kw)["selected_profiles"]}
        self.assertTrue({"motion designer", "ui interaction tester"} <= roles("design UI motion"))
        from vortex.skills import SkillEngine
        self.assertNotIn("motion designer", roles("UI motion", skills=SkillEngine(enabled=["android"])))

    def test_control_factories_escape_and_reject_invalid_attributes(self):
        from vortex.ui_components import Controls
        c = Controls()
        markup = c.toggle("demo", '<img src=x onerror=alert(1)>')
        self.assertIn("&lt;img", markup)
        self.assertNotIn("<img", markup)
        for id in ("demo", "motion-off", 'x" onclick="bad', "A"):
            with self.assertRaises(ValueError):
                c.toggle(id, "Label")
        with self.assertRaises(ValueError):
            c.radio("group", "Choices", ["A", "B"], selected=True)
        with self.assertRaises(ValueError):
            c.slider("slider", "Range", value=101)
        with self.assertRaises(ValueError):
            c.progress("progress", "Progress", value=-1)
        self.assertIn('name="group"', c.radio("group", "Choices", ["<A>", "B"]))
        with self.assertRaises(ValueError):
            c.text("group-0", "Collision")
        self.assertIn("&lt;A&gt;", c.select("select", "Theme", ["<A>", "B"]))

    def test_gallery_has_ten_unique_native_examples(self):
        class IDs(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
            def handle_starttag(self, tag, attrs):
                self.ids.extend(value for name, value in attrs if name == "id")
        parser = IDs()
        html = render_gallery()
        parser.feed(html)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertEqual(html.count('class="panel gallery-card"'), 10)
        self.assertIn("<select", html)
        self.assertIn('class="choice-rating"', html)

    def test_vector_motifs_are_fixed_and_decorative(self):
        from vortex.motion import motif_svg, stylesheet
        for name in ("shards", "ring", "slash", "spark", "cloud"):
            markup = motif_svg(name)
            self.assertIn('aria-hidden="true"', markup)
            self.assertNotIn("href=", markup)
        with self.assertRaises(ValueError):
            motif_svg('<script>')
        self.assertIn('--vx-impact-ms:420ms', stylesheet())
        self.assertIn('class="fx fx-shards"', render_menu())
        self.assertIn('class="fx fx-cloud"', render_gallery())

    def test_still_mode_reflects_state_and_palette_is_shared(self):
        from vortex.interface import COLORS
        html = render_menu(still=True)
        self.assertIn('id="motion-off" type="checkbox" checked disabled', html)
        self.assertIn("--bg:" + COLORS["background"], html)
        self.assertIn("--accent:" + COLORS["accent"], html)
        self.assertIn(":checked:not([checked])", render_gallery())
        with self.assertRaises(TypeError):
            COLORS["background"] = "#ffffff"
