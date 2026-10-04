import json
from pathlib import Path
import unittest

from calibration.run_calibration import strict_json, validate

ROOT = Path(__file__).resolve().parents[1]


class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "calibration/backend-response.schema.json").read_text(encoding="utf-8"))
        self.case = {"selected_text":"Ну ты и герой", "context":"Он спрятался."}
        self.value = {"term":"Ну ты и герой", "definition":"Ирония", "explanation":"Упрёк за трусость.", "examples":["Первый пример", "Второй пример"]}

    def test_rejects_markdown_duplicate_keys_and_nan(self):
        for raw in ('```json\n{}\n```', '{"term":"a","term":"b"}', '{"value":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)

    def test_rejects_string_instead_of_examples_array(self):
        self.value["examples"] = "Два примера"
        with self.assertRaises(ValueError):
            validate(self.value, self.case, self.schema)

    def test_rejects_changed_term_and_extra_fields(self):
        for change in ({"term":"герой"}, {"unknown":"value"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({**self.value, **change}, self.case, self.schema)

    def test_accepts_backend_contract(self):
        validate(self.value, self.case, self.schema)


if __name__ == "__main__":
    unittest.main()
