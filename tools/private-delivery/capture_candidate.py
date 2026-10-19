"""Retain a CLOSED, restored VM privately pending visual boot confirmation.

This is a diagnostic candidate, not the verified user transfer bundle.
Only use in a private/local destination approved by the owner.
"""
import argparse
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import vm_bundle as vm


def capture(documents, evidence, output, app_commit, backend_commit, stopped, qemu_img="qemu-img"):
    if not stopped:
        raise ValueError("Wait for the emulator process to exit before capturing")
    report = json.loads(evidence.read_text(encoding="utf-8-sig"))
    phases = report.get("observed_guest_phases", [])
    if (report.get("profile") != vm.PROFILE or report.get("setup_pending") is not False
            or not (report.get("patcher_done") is True or "done" in phases)
            or report.get("guest_kernel_panic") is not False or "panic" in phases
            or report.get("machine_running") is not True or report.get("guest_frame_received") is not True):
        raise ValueError("Cannot retain a successful-restore candidate from incomplete or panicked setup")
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (app_commit, backend_commit)):
        raise ValueError("Exact source commit IDs required")
    if output.exists():
        raise ValueError("Refusing to overwrite a candidate")
    files, source = vm.collect_files(documents)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="inferno-candidate-", dir=output.parent) as folder:
        folder = pathlib.Path(folder)
        disk = folder / "root.qcow2"
        subprocess.run([qemu_img, "convert", "-f", "qcow2" if source.suffix == ".qcow2" else "raw",
                        "-O", "qcow2", "-c", str(source), str(disk)], check=True)
        info = json.loads(subprocess.check_output([qemu_img, "info", "--output=json", str(disk)]))
        if info.get("backing-filename") or info.get("format") != "qcow2" or info.get("virtual-size", 0) <= 0:
            raise ValueError("Candidate disk must be standalone QCOW2")
        subprocess.run([qemu_img, "check", str(disk)], check=True)
        files["InfernoData/root.qcow2"] = disk
        # format0 deliberately cannot pass vm_bundle.verify's ready-kit check.
        meta = {"format": 0, "kind": "unverified-vm-candidate-v1", "profile": vm.PROFILE,
                "visible_springboard_confirmed": False, "app_commit": app_commit,
                "backend_commit": backend_commit, "files": {}}
        archive = folder / "candidate.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for name, file in sorted(files.items()):
                with file.open("rb") as stream:
                    meta["files"][name] = {"bytes": file.stat().st_size, "sha256": vm.digest(stream)}
                bundle.write(file, name)
            bundle.writestr("Candidate.json", json.dumps(meta, sort_keys=True, indent=2))
            bundle.writestr("Evidence.json", json.dumps(report, sort_keys=True, indent=2))
        # Validate the complete ZIP before publishing the private candidate.
        with zipfile.ZipFile(archive) as bundle:
            for name, expected in meta["files"].items():
                with bundle.open(name) as stream:
                    if bundle.getinfo(name).file_size != expected["bytes"] or vm.digest(stream) != expected["sha256"]:
                        raise ValueError("Candidate copy verification failed")
        try:
            os.link(archive, output)
        except FileExistsError:
            raise ValueError("Refusing to overwrite a candidate") from None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("documents", type=pathlib.Path)
    parser.add_argument("evidence", type=pathlib.Path)
    parser.add_argument("output", type=pathlib.Path)
    parser.add_argument("--app-commit", required=True)
    parser.add_argument("--backend-commit", required=True)
    parser.add_argument("--emulator-exited", action="store_true")
    args = parser.parse_args()
    capture(args.documents, args.evidence, args.output, args.app_commit, args.backend_commit, args.emulator_exited)
    print("Private candidate retained. SpringBoard remains UNVERIFIED; do not deliver as a ready kit.")
