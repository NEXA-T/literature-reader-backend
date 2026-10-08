import json
from pathlib import Path
import unittest
from calibration.run_calibration import strict_json, validate, validate_schema

ROOT = Path(__file__).resolve().parents[1]

class CalibrationTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "calibration/backend-response.schema.json").read_text(encoding="utf-8"))
        self.case = {"selected_text":"Ну ты и герой", "context":"Он спрятался."}
        self.value = {"translation":"Вот так храбрец!", "context_meaning":"Иронический упрёк за трусость.", "slang_or_etymology":None, "image_prompt":None}

    def test_accepts_nullable_fields(self):
        validate(self.value, self.case, self.schema)
        validate({**self.value, "image_prompt":"A frightened boy hiding under a table."}, self.case, self.schema)

    def test_rejects_old_contract_missing_fields_wrong_types(self):
        invalid = [{"term":"a","definition":"b","explanation":"c","examples":[]},
                   {k:v for k,v in self.value.items() if k != "image_prompt"},
                   {**self.value,"translation":None}, {**self.value,"image_prompt":[]},
                   {**self.value,"context_meaning":False}, {**self.value,"term":"old"}]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value, self.case, self.schema)

    def test_rejects_fake_null_empty_analysis_and_scene_without_context(self):
        for change in ({"slang_or_etymology":"null"}, {"translation":" "}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate({**self.value,**change},self.case,self.schema)
        with self.assertRaises(ValueError):
            validate({**self.value,"image_prompt":"A room."},{**self.case,"context":""},self.schema)

    def test_strict_json(self):
        for raw in ('```json\n{}\n```','{"x":1,"x":2}','{"x":NaN}','{} trailing'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                strict_json(raw)

    def test_request_and_error_contract(self):
        request = json.loads((ROOT / "calibration/request.schema.json").read_text(encoding="utf-8"))
        error = json.loads((ROOT / "calibration/error.schema.json").read_text(encoding="utf-8"))
        validate_schema(self.case,request)
        validate_schema({**self.case,"book_title":"Учебный пример"},request)
        for value in ({"selected_text":"a"},{**self.case,"context":None},{**self.case,"book_title":None}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate_schema(value,request)
        validate_schema({"error":"Повторите позже"},error)
        with self.assertRaises(ValueError):
            validate_schema({"error":None},error)

if __name__ == "__main__":
    unittest.main()
