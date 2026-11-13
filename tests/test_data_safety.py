import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class DataSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.datasets = root / "datasets"
        self.system = root / "system_data"
        self.datasets.mkdir()
        self.system.mkdir()
        self.addCleanup(patch.stopall)
        patch.object(app, "DATASETS_DIR", str(self.datasets)).start()
        patch.object(app, "SYSTEM_DATA_DIR", str(self.system)).start()
        patch.object(app, "DEFAULT_PROJECT_DIR", str(self.datasets / app.DEFAULT_PROJECT_FOLDER)).start()
        patch.object(app, "DEFAULT_CSV", str(self.datasets / app.DEFAULT_PROJECT_FOLDER / "manufacturing_defect_dataset.csv")).start()

    def test_startup_preserves_existing_default_tables(self):
        default_dir = self.datasets / app.DEFAULT_PROJECT_FOLDER
        default_dir.mkdir()
        (default_dir / "manufacturing_defect_dataset.csv").write_text("SupplierQuality,MaintenanceHours\n90,2\n", encoding="utf-8")
        db = self.system / app.DEFAULT_PROJECT_FOLDER / "workspace.db"
        db.parent.mkdir()
        conn = sqlite3.connect(db)
        with conn:
            for name in ("defects", "suppliers", "machines"):
                conn.execute(f'CREATE TABLE "{name}" (value TEXT)')
                conn.execute(f'INSERT INTO "{name}" VALUES (?)', ("user edit",))
        conn.close()
        app.init_db_and_notes()
        conn = sqlite3.connect(db)
        with conn:
            for name in ("defects", "suppliers", "machines"):
                self.assertEqual(conn.execute(f'SELECT value FROM "{name}"').fetchone()[0], "user edit")
        conn.close()

    def test_scan_updates_changed_source_and_preserves_notes(self):
        project = self.datasets / "sample"
        project.mkdir()
        source = project / "orders.csv"
        source.write_text("amount\n1\n", encoding="utf-8")
        imported, errors = app.scan_datasets_folders()
        self.assertEqual(imported, [("sample", "orders")])
        self.assertFalse(errors)
        notes = app.load_all_notes_dict("sample")
        notes["orders"] = [{"id": "note_custom", "title": "keep"}]
        app.save_all_notes_dict(notes, "sample")
        source.write_text("amount\n2\n", encoding="utf-8")
        imported, errors = app.scan_datasets_folders()
        self.assertEqual(imported, [("sample", "orders")])
        self.assertFalse(errors)
        conn = app.get_db_connection("sample")
        with conn:
            self.assertEqual(conn.execute('SELECT amount FROM "orders"').fetchone()[0], 2)
        conn.close()
        self.assertEqual(app.load_all_notes_dict("sample")["orders"], notes["orders"])

    def test_legacy_table_is_not_replaced_on_first_scan(self):
        project = self.datasets / "legacy"
        project.mkdir()
        (project / "orders.csv").write_text("amount\n2\n", encoding="utf-8")
        conn = app.get_db_connection("legacy")
        with conn:
            conn.execute('CREATE TABLE "orders" (amount INTEGER)')
            conn.execute('INSERT INTO "orders" VALUES (9)')
        conn.close()
        imported, errors = app.scan_datasets_folders()
        self.assertFalse(imported)
        self.assertFalse(errors)
        conn = app.get_db_connection("legacy")
        with conn:
            self.assertEqual(conn.execute('SELECT amount FROM "orders"').fetchone()[0], 9)
        conn.close()

    def test_first_import_preserves_preinstalled_lessons(self):
        project = self.datasets / "lessons"
        project.mkdir()
        (project / "orders.csv").write_text("amount\n1\n", encoding="utf-8")
        saved = [{"id": "note_course_01", "title": "Keep this lesson"}]
        app.save_all_notes_dict({"orders": saved}, "lessons")
        imported, errors = app.scan_datasets_folders()
        self.assertEqual(imported, [("lessons", "orders")])
        self.assertFalse(errors)
        self.assertEqual(app.load_all_notes_dict("lessons")["orders"], saved)

    def test_upload_uses_safe_filename(self):
        client = app.app.test_client()
        response = client.post("/api/upload_csv", data={
            "project_folder": "safe",
            "import_mode": "concat",
            "files": (io.BytesIO(b"amount\n1\n"), "../../outside.csv"),
        }, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertTrue((self.datasets / "safe" / "outside.csv").exists())
        self.assertFalse((self.datasets / "outside.csv").exists())


if __name__ == "__main__":
    unittest.main()
