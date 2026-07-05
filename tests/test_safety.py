"""Автоматические проверки безопасности и базовой логики Junk Cleaner."""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cleaner


FORBIDDEN_PREFIXES = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/Downloads"),
    os.path.expanduser("~/Pictures"),
    os.path.expanduser("~/Videos"),
    os.path.expanduser("~/Music"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Documents"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Desktop"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Downloads"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "System32"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "SysWOW64"),
]


def normalize(path: str) -> str:
    return os.path.normcase(os.path.normpath(path))


class SafetyTests(unittest.TestCase):
    def test_categories_exist(self):
        cats = cleaner.build_categories()
        self.assertGreaterEqual(len(cats), 8)
        keys = {c["key"] for c in cats}
        self.assertIn("user_temp", keys)
        self.assertIn("recycle_bin", keys)
        self.assertIn("dns", keys)

    def test_paths_do_not_touch_user_data(self):
        for cat in cleaner.build_categories():
            for base in cat.get("paths", []):
                if not base:
                    continue
                norm = normalize(base)
                for forbidden in FORBIDDEN_PREFIXES:
                    if not forbidden:
                        continue
                    f = normalize(forbidden)
                    self.assertFalse(
                        norm == f or norm.startswith(f + os.sep),
                        f"Категория {cat['key']} затрагивает запрещённый путь: {base}",
                    )

    def test_scan_all_categories_without_crash(self):
        for cat in cleaner.build_categories():
            try:
                size = cleaner.scan_category(cat)
            except Exception as exc:
                self.fail(f"scan_category упал для {cat['key']}: {exc}")
            self.assertGreaterEqual(size, 0)

    def test_human_size(self):
        self.assertIn("КБ", cleaner.human_size(2048))
        self.assertIn("МБ", cleaner.human_size(5 * 1024 * 1024))

    def test_dns_flush_runs(self):
        cleaner.flush_dns()

    def test_remove_path_only_deletes_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            keep = os.path.join(tmp, "keep.txt")
            remove = os.path.join(tmp, "remove.txt")
            with open(keep, "w", encoding="utf-8") as fh:
                fh.write("keep")
            with open(remove, "w", encoding="utf-8") as fh:
                fh.write("remove")
            size, count = cleaner.remove_path(remove)
            self.assertTrue(os.path.exists(keep))
            self.assertFalse(os.path.exists(remove))
            self.assertEqual(count, 1)
            self.assertGreater(size, 0)


class SmokeTests(unittest.TestCase):
    def test_exe_exists_on_desktop(self):
        desktop = os.path.join(os.environ["USERPROFILE"], "Desktop", "JunkCleaner.exe")
        self.assertTrue(os.path.isfile(desktop), "JunkCleaner.exe не найден на рабочем столе")

    def test_version_defined(self):
        self.assertEqual(cleaner.APP_VERSION, "1.0.0")


if __name__ == "__main__":
    unittest.main(verbosity=2)
