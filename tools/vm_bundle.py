"""Create/verify a LOCAL private VM transfer after confirmed boot and shutdown.

Never upload its output to the public repository or public workflow artifacts.
The ZIP expands directly to the application's Documents directory.
"""
import argparse
import hashlib
import json
import os
import pathlib
import plistlib
import re
import stat
import subprocess
import tempfile
import zipfile

PROFILE = "iphone12,1-18A5351d-v1"
DISKS = {"firmware": 8 << 20, "syscfg": 128 << 10, "ctrl_bits": 8 << 10,
         "nvram": 8 << 10, "effaceable": 4 << 10, "panic_log": 1 << 20,
         "sep_nvram": 64 << 10, "sep_ssc": 128 << 10}


def safe_path(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError("Invalid relative bundle path")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise ValueError("Invalid relative bundle path")
    return pathlib.PurePosixPath(value)


def regular(root, relative):
    relative = safe_path(relative)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlinks are not allowed in a machine bundle")
    if not stat.S_ISREG(current.stat().st_mode) or current.stat().st_size == 0:
        raise ValueError("A required machine file is empty or not regular")
    return current


def digest(stream):
    result = hashlib.sha256()
    while chunk := stream.read(1024 * 1024):
        result.update(chunk)
    return result.hexdigest()


def collect_files(documents):
    data = documents / "InfernoData"
    manifest = regular(documents, "InfernoData/Restore/BuildManifest.plist")
    with manifest.open("rb") as stream:
        firmware = plistlib.load(stream)
    if firmware.get("ProductBuildVersion") != "18A5351d":
        raise ValueError("This bundle profile requires build 18A5351d")
    identities = [item for item in firmware["BuildIdentities"]
                  if item.get("Info", {}).get("DeviceClass", "").lower() == "n104ap"
                  and "Erase" in item.get("Info", {}).get("Variant", "")]
    if len(identities) != 1:
        raise ValueError("Expected one n104ap erase identity")
    identity = identities[0]["Manifest"]
    selected = ["AppleSEPROM-Cebu-B1", "InfernoData/Restore/BuildManifest.plist",
                "InfernoData/root_ticket.der", "InfernoData/sep-firmware.n104.RELEASE.new.img4"]
    selected += ["InfernoData/" + name for name in DISKS]
    ramdisk = identity["RestoreRamDisk"]["Info"]["Path"]
    trust = identity.get("RestoreTrustCache", {}).get("Info", {}).get("Path")
    trust = trust or "Firmware/" + str(safe_path(ramdisk)) + ".trustcache"
    for component in (identity["KernelCache"]["Info"]["Path"],
                      identity["DeviceTree"]["Info"]["Path"], trust):
        selected.append("InfernoData/Restore/" + str(safe_path(component)))
    files = {name: regular(documents, name) for name in selected}
    for name, size in DISKS.items():
        if files["InfernoData/" + name].stat().st_size != size:
            raise ValueError("Unexpected state disk size: " + name)
    root = data / ("root.qcow2" if (data / "root.qcow2").exists() else "root")
    regular(documents, root.relative_to(documents).as_posix())
    return files, root


def verify(archive):
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP entries")
        for item in bundle.infolist():
            safe_path(item.filename)
            if stat.S_ISLNK(item.external_attr >> 16) or item.is_dir():
                raise ValueError("Only regular file entries are allowed")
        if "Machine.json" not in names:
            raise ValueError("Not a verified machine transfer bundle")
        meta_entry = bundle.getinfo("Machine.json")
        if meta_entry.file_size > 1024 * 1024:
            raise ValueError("Oversized bundle manifest")
        meta = json.loads(bundle.read(meta_entry))
        if meta.get("format") != 1 or meta.get("profile") != PROFILE:
            raise ValueError("Unsupported bundle profile")
        files = meta["files"]
        if not isinstance(files, dict) or set(names) != set(files) | {"Machine.json"}:
            raise ValueError("Bundle file set does not match its manifest")
        required = {"AppleSEPROM-Cebu-B1", "InfernoData/root.qcow2",
                    "InfernoData/root_ticket.der", "InfernoData/sep-firmware.n104.RELEASE.new.img4",
                    "InfernoData/Restore/BuildManifest.plist"} | {"InfernoData/" + name for name in DISKS}
        if not required.issubset(files):
            raise ValueError("Incomplete machine state")
        for name, expected in files.items():
            if bundle.getinfo(name).file_size != expected["bytes"]:
                raise ValueError("File length mismatch: " + name)
            with bundle.open(name) as stream:
                if digest(stream) != expected["sha256"]:
                    raise ValueError("File checksum mismatch: " + name)
        return meta


def create(documents, output, proof, app_commit, backend_commit, shutdown_confirmed, qemu_img):
    if not shutdown_confirmed:
        raise ValueError("Stop the guest and wait for the emulator to exit before exporting")
    for commit in (app_commit, backend_commit):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Record exact full source commit IDs")
    evidence = json.loads(proof.read_text(encoding="utf-8-sig"))
    if (evidence.get("profile") != PROFILE or evidence.get("visible_springboard_confirmed") is not True
            or evidence.get("patcher_done") is not True or evidence.get("setup_pending") is not False
            or evidence.get("guest_kernel_panic") is not False
            or "panic" in evidence.get("observed_guest_phases", [])
            or evidence.get("machine_running") is not True or evidence.get("guest_frame_received") is not True):
        raise ValueError("Confirmed SpringBoard and completed restore evidence is required")
    files, source = collect_files(documents)
    if output.exists():
        raise ValueError("Refusing to overwrite an existing bundle")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="inferno-transfer-", dir=output.parent) as temporary:
        temporary = pathlib.Path(temporary)
        disk = temporary / "root.qcow2"
        # qemu-img's normal exclusive image locking stays enabled. Never use -U.
        subprocess.run([qemu_img, "convert", "-f", "qcow2" if source.suffix == ".qcow2" else "raw",
                        "-O", "qcow2", "-c", str(source), str(disk)], check=True)
        info = json.loads(subprocess.check_output([qemu_img, "info", "--output=json", str(disk)]))
        if info.get("format") != "qcow2" or info.get("backing-filename") or info.get("virtual-size", 0) <= 0:
            raise ValueError("Exported root must be a standalone nonempty QCOW2 disk")
        subprocess.run([qemu_img, "check", str(disk)], check=True)
        files["InfernoData/root.qcow2"] = disk
        meta = {"format": 1, "profile": PROFILE, "app_commit": app_commit,
                "backend_commit": backend_commit, "files": {}}
        archive = temporary / "machine.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as bundle:
            for name, file in sorted(files.items()):
                with file.open("rb") as stream:
                    meta["files"][name] = {"bytes": file.stat().st_size, "sha256": digest(stream)}
                bundle.write(file, name)
            bundle.writestr("Machine.json", json.dumps(meta, sort_keys=True, indent=2))
        verify(archive)
        # The staging folder is on the destination filesystem. Link the closed,
        # verified ZIP atomically, without a partial copy or overwrite window.
        try:
            os.link(archive, output)
        except FileExistsError:
            raise ValueError("Refusing to overwrite an existing bundle") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("verify")
    check.add_argument("archive", type=pathlib.Path)
    export = commands.add_parser("create")
    export.add_argument("documents", type=pathlib.Path)
    export.add_argument("output", type=pathlib.Path)
    export.add_argument("--proof", type=pathlib.Path, required=True)
    export.add_argument("--app-commit", required=True)
    export.add_argument("--backend-commit", required=True)
    export.add_argument("--shutdown-confirmed", action="store_true")
    export.add_argument("--qemu-img", default="qemu-img")
    args = parser.parse_args()
    if args.command == "verify":
        verify(args.archive)
    else:
        create(args.documents, args.output, args.proof, args.app_commit, args.backend_commit,
               args.shutdown_confirmed, args.qemu_img)
    print("Local machine bundle verified. Keep this file private.")


if __name__ == "__main__":
    main()
