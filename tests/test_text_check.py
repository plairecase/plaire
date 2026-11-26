"""Тесты валидатора текстов. Запуск: python3 -m unittest discover -s tests"""
import unittest

from qc.text_check import check_bank, check_caption, check_item, check_screen, split_phrase


class Screen(unittest.TestCase):
    def ok(self, t, role="screen"):
        self.assertEqual(check_screen(t, role), [], t)

    def bad(self, t, role="screen"):
        self.assertNotEqual(check_screen(t, role), [], t)

    def test_good_examples(self):
        for t in ["Introducing Plaire.", "Stop keeping condoms in your wallet.",
                  "Holds 2. Feels like nothing.", "Eco-leather. Magnetic. Ultra-slim.",
                  "Carrying a condom case while clubbing >", "POV: no more crushed wrappers",
                  "€29 · Free EU shipping · plaire.eu", "Underrated case", "Holds two."]:
            self.ok(t)

    def test_forbidden(self):
        for t in ["Genuine leather.", "Real leather feel", "Leather-look case", "Snap closure",
                  "Discreet packaging", "Best-selling case", "The #1 case", "Sold out soon",
                  "Limited stock", "Rated by you", "Read the reviews"]:
            self.bad(t)

    def test_unverified(self):
        for t in ["Vegan and waterproof", "Handmade in Italy", "20% off today", "Big sale",
                  "Lifetime warranty", "Free returns"]:
            self.bad(t)

    def test_facts(self):
        self.bad("Only €25")
        self.bad("Holds 3")
        self.bad("Holds three condoms")
        self.bad("30-day returns")
        self.bad("Free delivery")
        self.bad("Free shipping worldwide")
        self.bad("Leather case")
        self.ok("14-day returns")
        self.ok("Free shipping to all EU countries")

    def test_form(self):
        self.bad("one two three four five six seven")
        self.bad("Wow!")
        self.bad("Nice case 🔥")
        self.bad("BEST CASE")
        self.ok("PLAIRE — ECO-LEATHER CASE", role="eyebrow")
        self.bad("#condomcase")


class Split(unittest.TestCase):
    def test_split_keeps_limit(self):
        s = split_phrase("Tell me you're prepared without telling me")
        self.assertGreater(len(s), 1)
        for part in s:
            self.assertEqual(check_screen(part), [], part)

    def test_short_not_split(self):
        self.assertEqual(split_phrase("Introducing Plaire."), ["Introducing Plaire."])


class Item(unittest.TestCase):
    def test_native_no_eyebrow(self):
        self.assertNotEqual(check_item({"style": "native", "screens": ["Hi there"], "eyebrow": "X"}), [])

    def test_native_max_two_screens(self):
        self.assertNotEqual(check_item({"style": "native", "screens": ["a b", "c d", "e f"]}), [])


class Caption(unittest.TestCase):
    TT = "Finally, a real condom case.\nLooks like a mini wallet.\nLink in bio — plaire.eu\n#condomcase #plaire #datenight"
    IG = "The condom case, redesigned.\nEco-leather. Holds 2.\nLink in bio — plaire.eu\n#condomcase #plaire #eco"

    def test_good(self):
        self.assertEqual(check_caption(self.TT, "tiktok"), [])
        self.assertEqual(check_caption(self.IG, "instagram"), [])

    def test_sound_line_ignored(self):
        self.assertEqual(check_caption(self.TT + "\n[sound: Track, 120 BPM, from 12s]", "tiktok"), [])

    def test_bad(self):
        self.assertNotEqual(check_caption(self.TT + " #fyp", "tiktok"), [])
        self.assertNotEqual(check_caption("Nice.\n#a #b", "tiktok"), [])
        no_kw = "Nice case.\nplaire.eu\n#condomcase #plaire #x"
        self.assertNotEqual(check_caption(no_kw, "tiktok"), [])
        self.assertEqual(check_caption(no_kw, "tiktok", screen_texts=["Finally, a real condom case."]), [])


class Bank(unittest.TestCase):
    def test_texts_json_passes(self):
        self.assertEqual(check_bank(), [])


if __name__ == "__main__":
    unittest.main()
