import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import app
from olist_sql_lessons import OLIST_SQL_LESSONS, install
from olist_column_dictionary import FIELDS, install as install_dictionary


class OlistLessonsTests(unittest.TestCase):
    def test_dictionary_covers_all_imported_columns(self):
        db = Path(app.SYSTEM_DATA_DIR) / "03_Olist_Brazilian_Ecommerce" / "workspace.db"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "column_dictionary.json"
            path.write_text(json.dumps({"olist_orders_dataset": {"order_id": {"zh": "自訂", "purpose": "保留"}}}), encoding="utf-8")
            self.assertEqual(install_dictionary(path, db), 46)
            self.assertEqual(install_dictionary(path, db), 0)
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual({k: len(v) for k, v in data.items()}, {k: len(v) for k, v in FIELDS.items()})
            self.assertEqual(data["olist_orders_dataset"]["order_id"]["zh"], "自訂")

    def test_all_sql_lessons_run_and_install_is_idempotent(self):
        project = "03_Olist_Brazilian_Ecommerce"
        db = Path(app.SYSTEM_DATA_DIR) / project / "workspace.db"
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            self.assertEqual(len(OLIST_SQL_LESSONS), 12)
            for note in OLIST_SQL_LESSONS:
                with self.subTest(note=note["id"]):
                    cursor = conn.execute(note["sql"])
                    self.assertIsNotNone(cursor.fetchone())
        finally:
            conn.close()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "saved_queries.json"
            path.write_text(json.dumps({"olist_orders_dataset": [{"id": "existing"}]}), encoding="utf-8")
            self.assertEqual(install(path), 12)
            self.assertEqual(install(path), 0)
            notes = json.loads(path.read_text(encoding="utf-8"))["olist_orders_dataset"]
            self.assertEqual(len(notes), 13)
            self.assertEqual(notes[0]["id"], "existing")


if __name__ == "__main__":
    unittest.main()
