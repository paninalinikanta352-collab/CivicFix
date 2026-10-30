import unittest

from ai_service import calculate_risk_percentage as risk


class CalculateRiskTests(unittest.TestCase):
    # NOTE: signature is (category, description, location="").

    def test_api_category_baselines(self):
        self.assertEqual(risk("roads", "Please inspect this issue"), 40)
        self.assertEqual(risk("water", "Please inspect this issue"), 40)
        self.assertEqual(risk("electricity", "Please inspect this issue"), 40)
        self.assertEqual(risk("cleanliness", "Please inspect this issue"), 40)
        self.assertEqual(risk("other", "Please inspect this issue"), 10)

    def test_high_risk_description_beats_low_baseline(self):
        self.assertEqual(risk("other", "There is a gas leak"), 80)

    def test_medium_risk_description_with_unknown_category(self):
        self.assertEqual(risk("other", "A pothole is on the road"), 45)

    def test_low_risk_input(self):
        self.assertEqual(risk("other", "A public bench needs paint"), 10)

    def test_sensitive_location_bonus(self):
        self.assertEqual(risk("other", "A public bench needs paint", "Near the school"), 20)

    def test_location_is_optional(self):
        self.assertEqual(risk("other", "A public bench needs paint", ""), 10)
        self.assertEqual(risk("other", "A public bench needs paint"), 10)

    def test_matching_is_case_insensitive_and_normalizes_whitespace(self):
        self.assertEqual(risk(" other ", "  GAS   LEAK ", "PUNE"), 80)

    def test_repeated_keywords_only_apply_one_bonus(self):
        self.assertEqual(risk("other", "Fire fire FIRE", "Pune"), 80)

    def test_keyword_matching_uses_word_boundaries(self):
        self.assertEqual(risk("other", "Fireworks are planned", "Pune"), 10)

    def test_sensitive_location_stacks_on_medium_keyword(self):
        self.assertEqual(risk("electricity", "Broken streetlight outside the school gate", "Near the school"), 55)

    def test_scores_stay_within_range(self):
        examples = [
            ("other", "fire accident flood explosion", "school market"),
            ("other", "All good", "Pune"),
            ("roads", "Dangerous blocking the way", "highway"),
        ]
        for args in examples:
            with self.subTest(args=args):
                self.assertIn(risk(*args), range(101))

    def test_inputs_must_be_strings(self):
        for args in (("other", 5), ("other", "Issue", 5), ("other", "Issue", [])):
            with self.subTest(args=args), self.assertRaises(TypeError):
                risk(*args)

    def test_category_and_description_must_be_non_empty(self):
        for args in (("", "Issue"), (" ", "Issue"), ("other", ""), ("other", "   ")):
            with self.subTest(args=args), self.assertRaises(ValueError):
                risk(*args)


if __name__ == "__main__":
    unittest.main()
