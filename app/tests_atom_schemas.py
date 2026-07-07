from django.test import SimpleTestCase
from pydantic import ValidationError as PydanticValidationError

from app.atom_schemas import (
    format_pydantic_errors,
    validate_content_cards,
    validate_quiz_data,
)


class AtomSchemaTests(SimpleTestCase):
    def test_validate_content_cards_success(self):
        cards = validate_content_cards(
            [
                {"card_index": 0, "content_type": "markdown", "content_body": "Hi"},
                {"card_index": 1, "content_type": "code", "content_body": "x = 1"},
            ]
        )
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["content_type"], "markdown")

    def test_validate_content_cards_rejects_bad_index(self):
        with self.assertRaises(PydanticValidationError):
            validate_content_cards(
                [
                    {"card_index": 0, "content_type": "markdown", "content_body": "Hi"},
                    {"card_index": 2, "content_type": "code", "content_body": "x = 1"},
                ]
            )

    def test_validate_quiz_data_success(self):
        quiz = validate_quiz_data(
            {
                "options": ["A", "B", "C"],
                "correct_index": 1,
                "explanation": "Because B.",
            }
        )
        self.assertEqual(quiz["correct_index"], 1)

    def test_validate_quiz_data_rejects_wrong_option_count(self):
        with self.assertRaises(PydanticValidationError):
            validate_quiz_data(
                {
                    "options": ["A", "B"],
                    "correct_index": 0,
                    "explanation": "Nope.",
                }
            )

    def test_format_pydantic_errors(self):
        try:
            validate_quiz_data({"options": ["A"], "correct_index": 0, "explanation": ""})
        except PydanticValidationError as exc:
            messages = format_pydantic_errors(exc)
            self.assertTrue(messages)
