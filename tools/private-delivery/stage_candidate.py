"""Stage a private UNVERIFIED candidate in a new folder for normal cold-boot testing.

This never produces a verified transfer bundle or merges an existing machine.
"""
import argparse
import json
import os
import pathlib
import re
import stat
import sys
import tempfile
import zipfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import vm_bundle as vm


def stage(archive, destination):
    if destination.exists() or destination.is_symlink():
        raise ValueError("Refusing to merge or overwrite a machine folder")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive entries")
        for item in bundle.infolist():
            vm.safe_path(item.filename)
            if item.is_dir() or stat.S_ISLNK(item.external_attr >> 16):
                raise ValueError("Only regular file entries are allowed")
        for name in ("Candidate.json", "Evidence.json"):
            if name not in names or bundle.getinfo(name).file_size > 1024 * 1024:
                raise ValueError("Missing or oversized candidate metadata")
        meta = json.loads(bundle.read("Candidate.json"))
        if (meta.get("format") != 0 or meta.get("kind") != "unverified-vm-candidate-v1"
                or meta.get("profile") != vm.PROFILE
                or meta.get("visible_springboard_confirmed") is not False
                or not all(re.fullmatch(r"[0-9a-f]{40}", meta.get(key, ""))
                           for key in ("app_commit", "backend_commit"))):
            raise ValueError("Unsupported private candidate metadata")
        files = meta.get("files")
        if not isinstance(files, dict) or set(names) != set(files) | {"Candidate.json", "Evidence.json"}:
            raise ValueError("Candidate file set mismatch")
        # Only machine inputs can reach Documents. In particular a checkpoint,
        # defaults file or executable can never sneak in as an extra member.
        fixed = {"AppleSEPROM-Cebu-B1", "InfernoData/root.qcow2", "InfernoData/root_ticket.der",
                 "InfernoData/sep-firmware.n104.RELEASE.new.img4"}
        fixed |= {"InfernoData/" + name for name in vm.DISKS}
        if not fixed.issubset(files):
            raise ValueError("Incomplete candidate state")
        if any(name not in fixed and not name.startswith("InfernoData/Restore/") for name in files):
            raise ValueError("Unexpected machine input")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="inferno-cold-boot-", dir=destination.parent) as folder:
            staged = pathlib.Path(folder) / "Documents"
            staged.mkdir()
            for name, expected in files.items():
                entry = bundle.getinfo(name)
                if entry.file_size != expected["bytes"] or entry.file_size <= 0:
                    raise ValueError("Candidate file length mismatch")
                target = staged.joinpath(*vm.safe_path(name).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(name) as source, target.open("xb") as output:
                    while chunk := source.read(1024 * 1024):
                        output.write(chunk)
                with target.open("rb") as source:
                    if vm.digest(source) != expected["sha256"]:
                        raise ValueError("Candidate checksum mismatch")
            # Validate manifest-derived boot files and all state sizes too.
            vm.collect_files(staged)
            # rename refuses an occupied nonempty directory, and the destination
            # is never removed or merged. This tool runs in an isolated CI folder.
            if destination.exists() or destination.is_symlink():
                raise ValueError("Refusing to overwrite a machine folder")
            os.rename(staged, destination)
    return meta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=pathlib.Path)
    parser.add_argument("destination", type=pathlib.Path)
    args = parser.parse_args()
    stage(args.archive, args.destination)
    print("Unverified candidate staged in a new folder. Cold boot and visual confirmation remain required.")
