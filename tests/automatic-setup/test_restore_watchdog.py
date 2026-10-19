"""Privacy boundary checks; these tests never boot a guest."""
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

path = pathlib.Path(__file__).parents[2] / "tools/restore_watchdog.py"
spec = importlib.util.spec_from_file_location("restore_watchdog", path)
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


class WatchdogTests(unittest.TestCase):
    def test_raw_addresses_arguments_paths_and_unknown_symbols_cannot_escape(self):
        raw = "private-name /private/user/secret 0x1234 unknown_private_function\n"
        raw += "  2 dwc3_td_fetch + 123 (address 0xabcdef)\n  readv read __ulock_wait2\n"
        report = watchdog.summarize(raw)
        self.assertEqual(set(report), set(watchdog.SYMBOLS))
        self.assertEqual(report["dwc3_td_fetch"], 1)
        self.assertEqual(report["read"], 1)
        self.assertEqual(report["__ulock_wait"], 0)
        self.assertEqual(report["__ulock_wait2"], 1)
        serialized = json.dumps(report)
        for forbidden in ("private-name", "/private/", "0x1234", "unknown_private_function", "abcdef"):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(all(isinstance(value, int) and value >= 0 for value in report.values()))

    @unittest.skipUnless(sys.platform == "darwin", "Actual sample tool is macOS only")
    def test_real_host_child_sample_contains_only_bounded_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            child = subprocess.Popen(["/bin/sleep", "10"])
            try:
                watchdog.sample(child.pid, pathlib.Path(folder), 1)
            finally:
                child.terminate()
                child.wait()
            report = json.loads((pathlib.Path(folder) / "host-stall-1.json").read_text())
            self.assertEqual(report.get("sample_exit"), 0, "Host sampling must actually work on this runner")
            self.assertFalse(report["guest_memory_exported"])
            self.assertFalse(report["raw_stack_exported"])
            self.assertLessEqual(set(report["known_stack_symbols"]), set(watchdog.SYMBOLS))
            self.assertLess(len(json.dumps(report)), 4096)
            self.assertEqual(list(pathlib.Path(folder).iterdir()), [pathlib.Path(folder) / "host-stall-1.json"])


if __name__ == "__main__":
    unittest.main()
