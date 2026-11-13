"""Exercise every lesson through the same APIs used by the workbench."""

import shutil
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

import app
from learning_notes import DEFECTS_LEARNING_NOTES


class LearningNotesTests(unittest.TestCase):
    def test_all_lessons_run_on_isolated_demo_database(self):
        project = app.DEFAULT_PROJECT_FOLDER
        source_db = Path(app.SYSTEM_DATA_DIR) / project / "workspace.db"
        with tempfile.TemporaryDirectory() as tmp:
            target_dir = Path(tmp) / project
            target_dir.mkdir()
            shutil.copy2(source_db, target_dir / "workspace.db")
            with patch.object(app, "SYSTEM_DATA_DIR", tmp):
                client = app.app.test_client()
                self.assertEqual(len(DEFECTS_LEARNING_NOTES), 10)
                self.assertEqual(len({n["id"] for n in DEFECTS_LEARNING_NOTES}), 10)
                for note in DEFECTS_LEARNING_NOTES:
                    endpoint = "/api/query" if note["lang"] == "sql" else "/api/run_python"
                    field = "sql" if note["lang"] == "sql" else "code"
                    with self.subTest(note=note["id"]):
                        response = client.post(endpoint, json={
                            field: note["sql"], "table": "defects", "folder": project
                        })
                        self.assertEqual(response.status_code, 200, response.get_json())
                        payload = response.get_json()
                        table = payload if note["lang"] == "sql" else payload["table_data"]
                        self.assertIsNotNone(table)
                        self.assertGreater(table["total_rows"], 0)

                notes_file = target_dir / "saved_queries.json"
                notes_file.write_text(json.dumps({"defects": DEFECTS_LEARNING_NOTES}), encoding="utf-8")
                response = client.post("/api/reset_default_notes", json={
                    "table": "defects", "folder": project, "target_col": "DefectStatus"
                })
                self.assertEqual(response.status_code, 200, response.get_json())
                returned_ids = {n["id"] for n in response.get_json()["notes"]}
                self.assertTrue({n["id"] for n in DEFECTS_LEARNING_NOTES}.issubset(returned_ids))


if __name__ == "__main__":
    unittest.main()
