"""Safety scenarios; no real guest is started, stopped, or written by these tests."""
import json
import unittest
from unittest.mock import Mock, patch

import device_lifecycle as vm


class LifecycleSafety(unittest.TestCase):
    def test_restart_never_starts_after_failed_stop(self):
        with patch.object(vm, "stop", side_effect=RuntimeError("still running")), \
                patch.object(vm, "start") as start:
            with self.assertRaises(RuntimeError):
                vm.restart()
            start.assert_not_called()

    def test_disconnected_quit_requires_observed_container_exit(self):
        with patch.object(vm, "inspect_vm", side_effect=[
                {"State": {"Running": True}}, {"State": {"Running": False}}]), \
                patch.object(vm, "execute", side_effect=ConnectionError("closed")) as qmp:
            self.assertEqual(vm.stop(), "stopped")
            qmp.assert_called_once_with("quit")

    def test_running_vm_is_not_started_twice(self):
        with patch.object(vm, "docker", return_value=Mock(returncode=0)), \
                patch.object(vm, "inspect_vm", return_value={"State": {"Running": True}}), \
                patch.object(vm, "execute", return_value={"running": True}), \
                patch.object(vm, "ensure_exclusive") as exclusive:
            self.assertEqual(vm.start(), "running")
            self.assertEqual(vm.docker.call_count, 1)  # engine availability only
            exclusive.assert_not_called()

    def test_running_writer_blocks_disk_reuse(self):
        writer = [{"Mounts": [{"Source": str(vm.VM), "RW": True}]}]
        with patch.object(vm, "docker", side_effect=[
                Mock(returncode=0, stdout="other-vm\n"),
                Mock(returncode=0, stdout=json.dumps(writer))]):
            with self.assertRaises(RuntimeError):
                vm.ensure_exclusive()

    def test_unknown_configuration_cannot_be_stopped(self):
        info = {"Config": {"Image": "unrelated", "Cmd": []}, "Mounts": []}
        with patch.object(vm, "docker", return_value=Mock(returncode=0, stdout=json.dumps([info]))), \
                patch.object(vm, "execute") as qmp:
            with self.assertRaises(RuntimeError):
                vm.stop()
            qmp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
