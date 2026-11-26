import unittest

from vortex.conversation import Conversation, GREETING


class ConversationTests(unittest.TestCase):
    def test_exact_greeting_and_case_variants(self):
        expected = "🇮🇪 𝘏𝘦𝘭𝘭𝘰, 𝘐’𝘮 𝘝𝘰𝘳𝘵𝘦𝘹\n𝘏𝘰𝘸 𝘤𝘢𝘯 𝘐 𝘩𝘦𝘭𝘱 𝘺𝘰𝘶 𝘳𝘪𝘨𝘩𝘵 𝘯𝘰𝘸?"
        self.assertEqual(GREETING, expected)
        for trigger in ("Vortex", "vorteX", "VORTEX", "🇮🇪", "  vortex  "):
            with self.subTest(trigger=trigger):
                session = Conversation(locale="pt-BR")
                self.assertEqual(session.handle(trigger)["text"],
                                 expected + "\n\nVocê quer ver o menu?")
                self.assertEqual(session.handle(trigger)["kind"], "already_active")

    def test_no_implicit_or_substring_activation(self):
        for text in ("Vortex please", "🇮🇪 🇮🇪", "not vortex", "Vortex!", "menu"):
            self.assertEqual(Conversation().handle(text)["kind"], "pass_through")

    def test_session_state_is_not_shared(self):
        first, second = Conversation(), Conversation()
        first.handle("Vortex")
        self.assertEqual(second.handle("yes")["kind"], "pass_through")
        self.assertEqual(second.handle("Vortex")["kind"], "greeting")

    def test_menu_acceptance_navigation_and_fallback(self):
        session = Conversation(locale="pt")
        session.handle("🇮🇪")
        menu = session.handle("sim")
        self.assertEqual(len(menu["entries"]), 6)
        self.assertFalse(menu["interactive_supported"])
        self.assertIn("1. Agentes", menu["text"])
        self.assertEqual(session.handle("2")["section"], "functions")
        self.assertEqual(session.handle("0")["section"], None)
        self.assertEqual(session.handle("segurança")["section"], "security")

    def test_menu_discloses_planning_and_bound_tools(self):
        session = Conversation(enabled={"android", "engineering"},
                               execution_capabilities={"android"}, interactive=True)
        session.handle("Vortex")
        self.assertTrue(session.handle("menu")["interactive_supported"])
        rows = session.handle("functions")["entries"]
        self.assertEqual({row["id"] for row in rows}, {"android", "engineering"})
        self.assertEqual(rows[1]["status"], "planning")
        self.assertIn("android engineer", rows[0]["agents"])
        self.assertEqual([row["id"] for row in session.handle("tools")["entries"]],
                         ["android"])
        self.assertFalse(session.handle("security")["delivery_authorized"])

    def test_no_execution_claim_by_default(self):
        session = Conversation()
        session.handle("Vortex")
        session.handle("menu")
        self.assertEqual(session.handle("tools")["entries"], [])

    def test_direct_request_runs_economy_without_menu(self):
        session = Conversation()
        session.handle("Vortex")
        task = "  build an Android APK  "
        result = session.handle(task)
        self.assertEqual(result["task"], task)
        self.assertEqual(result["kind"], "task")
        self.assertTrue(result["plan"]["economy"]["mandatory_review_roles_preserved"])
        self.assertFalse(result["delivery_authorized"])
        self.assertEqual(session.handle("yes")["kind"], "task")

    def test_decline_menu_and_request_later(self):
        session = Conversation()
        session.handle("Vortex")
        self.assertEqual(session.handle("no")["kind"], "prompt")
        self.assertEqual(session.handle("menu")["kind"], "menu")

    def test_invalid_inputs_and_host_claims_rejected(self):
        with self.assertRaises(ValueError):
            Conversation(enabled={"android"}, execution_capabilities={"research"})
        with self.assertRaises(ValueError):
            Conversation(interactive="true")
        for value in ("", " ", "x" * 8193, None):
            with self.assertRaises(ValueError):
                Conversation().handle(value)

    def test_cli_session(self):
        import contextlib
        import io
        import json
        from vortex.cli import main

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["chat", "--locale", "pt", "Vortex", "sim", "2"]), 0)
        events = json.loads(output.getvalue())
        self.assertEqual([event["kind"] for event in events], ["greeting", "menu", "menu"])
        self.assertEqual(events[-1]["section"], "functions")
