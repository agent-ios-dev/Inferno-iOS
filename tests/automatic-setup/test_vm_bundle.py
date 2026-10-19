"""Synthetic transfer fixtures only; these tests do not boot iOS."""
import importlib.util
import json
import pathlib
import plistlib
import shutil
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location("vm_bundle", pathlib.Path(__file__).parents[2] / "tools/vm_bundle.py")
vm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vm)


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)

    def fixture(self):
        def put(name, data=b"fixture"):
            file = self.root / name
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(data)
        for name, size in vm.DISKS.items():
            file = self.root / "InfernoData" / name
            file.parent.mkdir(parents=True, exist_ok=True)
            with file.open("wb") as stream:
                stream.truncate(size)
        for name in ("AppleSEPROM-Cebu-B1", "InfernoData/root_ticket.der",
                     "InfernoData/sep-firmware.n104.RELEASE.new.img4", "InfernoData/root",
                     "InfernoData/Restore/kernel", "InfernoData/Restore/tree",
                     "InfernoData/Restore/Firmware/ramdisk.dmg.trustcache"):
            put(name)
        manifest = {"ProductBuildVersion": "18A5351d", "BuildIdentities": [{
            "Info": {"DeviceClass": "n104ap", "Variant": "Customer Erase Install (IPSW)"},
            "Manifest": {key: {"Info": {"Path": value}} for key, value in
                         {"KernelCache": "kernel", "DeviceTree": "tree", "RestoreRamDisk": "ramdisk.dmg"}.items()}}]}
        put("InfernoData/Restore/BuildManifest.plist", plistlib.dumps(manifest))

    def archive(self, mutate=None, extra=None, drop=None):
        self.fixture()
        files, _ = vm.collect_files(self.root)
        files["InfernoData/root.qcow2"] = self.root / "InfernoData/root"
        if drop:
            del files[drop]
        meta = {"format": 1, "profile": vm.PROFILE, "files": {}}
        for name, path in files.items():
            with path.open("rb") as stream:
                meta["files"][name] = {"bytes": path.stat().st_size, "sha256": vm.digest(stream)}
        if mutate:
            mutate(meta)
        output = self.root / "test.zip"
        with zipfile.ZipFile(output, "w") as bundle:
            for name, path in files.items():
                bundle.write(path, name)
            bundle.writestr("Machine.json", json.dumps(meta))
            if extra:
                bundle.writestr(extra, b"unexpected")
        return output

    def test_complete_state_and_no_downloads(self):
        self.fixture()
        files, root = vm.collect_files(self.root)
        self.assertEqual(root.name, "root")
        self.assertTrue(all("InfernoData/" + name in files for name in vm.DISKS))
        self.assertFalse(any(name.endswith(".ipsw") or "SetupDownloads" in name for name in files))

    def test_path_traversal_and_symlink_rejected(self):
        for name in ("../root", "/root", "C:/root", "Restore\\root", "a//b"):
            with self.assertRaises(ValueError):
                vm.safe_path(name)
        target = self.root / "target"
        target.write_bytes(b"private")
        link = self.root / "link"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("Host does not permit symlink creation")
        with self.assertRaises(ValueError):
            vm.regular(self.root, "link")

    def test_archive_hash_and_file_set(self):
        self.assertEqual(vm.verify(self.archive())["profile"], vm.PROFILE)

    def test_tampered_hash_rejected(self):
        with self.assertRaisesRegex(ValueError, "checksum"):
            vm.verify(self.archive(lambda meta: meta["files"]["InfernoData/root.qcow2"].update(sha256="0" * 64)))

    def test_unexpected_entry_rejected(self):
        with self.assertRaises(ValueError):
            vm.verify(self.archive(extra="guest-console.log"))

    def test_unsafe_archive_path_rejected(self):
        with self.assertRaises(ValueError):
            vm.verify(self.archive(extra="../outside"))

    def test_missing_sep_state_rejected(self):
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            vm.verify(self.archive(drop="InfernoData/sep_nvram"))

    @unittest.skipUnless(shutil.which("qemu-img"), "Requires the real qemu-img converter")
    def test_real_converter_and_no_overwrite(self):
        self.fixture()
        proof = self.root / "proof.json"
        proof.write_text(json.dumps({"profile": vm.PROFILE, "visible_springboard_confirmed": True,
                                   "patcher_done": True, "setup_pending": False, "guest_kernel_panic": False,
                                   "machine_running": True, "guest_frame_received": True}))
        output = self.root / "machine.zip"
        vm.create(self.root, output, proof, "a" * 40, "b" * 40, True, "qemu-img")
        verified = vm.verify(output)
        self.assertIn("InfernoData/root.qcow2", verified["files"])
        with zipfile.ZipFile(output) as bundle:
            self.assertEqual(bundle.read("InfernoData/root.qcow2")[:4], b"QFI\xfb")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            vm.create(self.root, output, proof, "a" * 40, "b" * 40, True, "qemu-img")

    def test_export_refuses_without_shutdown_or_boot_proof(self):
        proof = self.root / "proof.json"
        proof.write_text(json.dumps({"profile": vm.PROFILE, "visible_springboard_confirmed": False}))
        for stopped in (False, True):
            with self.assertRaises(ValueError):
                vm.create(self.root, self.root / "out.zip", proof, "a" * 40, "b" * 40, stopped, "missing-qemu-img")
        self.assertFalse((self.root / "out.zip").exists())

    def capture_module(self):
        location = pathlib.Path(vm.__file__).parent / "private-delivery/capture_candidate.py"
        capture_spec = importlib.util.spec_from_file_location("capture_candidate", location)
        module = importlib.util.module_from_spec(capture_spec)
        capture_spec.loader.exec_module(module)
        return module

    def test_private_capture_refuses_unfinished_restore(self):
        report = self.root / "report.json"
        report.write_text(json.dumps({"profile": vm.PROFILE, "setup_pending": True}))
        with self.assertRaises(ValueError):
            self.capture_module().capture(self.root, report, self.root / "candidate.zip", "a" * 40, "b" * 40, True)
        self.assertFalse((self.root / "candidate.zip").exists())

    @unittest.skipUnless(shutil.which("qemu-img"), "Requires the real qemu-img converter")
    def test_private_candidate_is_not_a_ready_transfer(self):
        self.fixture()
        report = self.root / "report.json"
        report.write_text(json.dumps({"profile": vm.PROFILE, "setup_pending": False,
                                     "guest_kernel_panic": False, "observed_guest_phases": ["done"],
                                     "visible_springboard_confirmed": False,
                                     "machine_running": True, "guest_frame_received": True}))
        output = self.root / "candidate.zip"
        self.capture_module().capture(self.root, report, output, "a" * 40, "b" * 40, True)
        with zipfile.ZipFile(output) as bundle:
            meta = json.loads(bundle.read("Candidate.json"))
            self.assertFalse(meta["visible_springboard_confirmed"])
            self.assertEqual(meta["kind"], "unverified-vm-candidate-v1")
        with self.assertRaisesRegex(ValueError, "Not a verified"):
            vm.verify(output)

    def test_crashed_guest_or_missing_frame_is_not_ready(self):
        valid = {"profile": vm.PROFILE, "visible_springboard_confirmed": True,
                 "patcher_done": True, "setup_pending": False, "guest_kernel_panic": False,
                 "machine_running": True, "guest_frame_received": True}
        proof = self.root / "proof.json"
        for field in ("machine_running", "guest_frame_received"):
            proof.write_text(json.dumps(dict(valid, **{field: False})))
            with self.assertRaises(ValueError):
                vm.create(self.root, self.root / "out.zip", proof, "a" * 40, "b" * 40, True, "missing-qemu-img")
        proof.write_text(json.dumps(dict(valid, observed_guest_phases=["panic"])))
        with self.assertRaises(ValueError):
            vm.create(self.root, self.root / "out.zip", proof, "a" * 40, "b" * 40, True, "missing-qemu-img")

    def staging_fixture(self, mutate=None, extra=None):
        source = self.archive(mutate=mutate)
        output = self.root / "candidate-fixture.zip"
        with zipfile.ZipFile(source) as original, zipfile.ZipFile(output, "w") as candidate:
            meta = json.loads(original.read("Machine.json"))
            meta.update(format=0, kind="unverified-vm-candidate-v1", app_commit="a" * 40,
                        backend_commit="b" * 40, visible_springboard_confirmed=False)
            for item in original.infolist():
                if item.filename != "Machine.json":
                    candidate.writestr(item, original.read(item))
            candidate.writestr("Candidate.json", json.dumps(meta))
            candidate.writestr("Evidence.json", "{}")
            if extra:
                candidate.writestr(extra, "unexpected")
        location = pathlib.Path(vm.__file__).parent / "private-delivery/stage_candidate.py"
        module_spec = importlib.util.spec_from_file_location("stage_candidate", location)
        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return output, module

    def test_stage_candidate_preserves_only_machine_inputs(self):
        archive, module = self.staging_fixture()
        destination = self.root / "fresh-documents"
        module.stage(archive, destination)
        files, root = vm.collect_files(destination)
        self.assertEqual(root.name, "root.qcow2")
        self.assertTrue(files)
        self.assertFalse((destination / "AutomaticSetup.plist").exists())
        self.assertFalse((destination / "Candidate.json").exists())
        with self.assertRaisesRegex(ValueError, "overwrite"):
            module.stage(archive, destination)

    def test_stage_rejects_traversal_and_extra_files(self):
        for extra in ("../escaped", "AutomaticSetup.plist", "guest-console.log"):
            archive, module = self.staging_fixture(extra=extra)
            destination = self.root / "must-not-appear"
            with self.assertRaises(ValueError):
                module.stage(archive, destination)
            self.assertFalse(destination.exists())
        self.assertFalse((self.root / "escaped").exists())

    def test_stage_checksum_failure_never_publishes_folder(self):
        archive, module = self.staging_fixture(
            mutate=lambda meta: meta["files"]["InfernoData/root.qcow2"].update(sha256="0" * 64))
        destination = self.root / "corrupted-documents"
        with self.assertRaisesRegex(ValueError, "checksum"):
            module.stage(archive, destination)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
