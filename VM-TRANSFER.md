# Private machine transfer from a computer to iPhone

No working guest bundle is provided yet. The restore/boot investigation must
first establish real SpringBoard. The packaging tool is not boot evidence.

`tools/vm_bundle.py` packages the installed machine locally, not an IPSW.
It keeps the system disk and every SEP/NVRAM/device-state disk together,
plus the manifest-selected kernel, DeviceTree, trust cache and boot assets.
It excludes downloaded IPSWs, restore filesystem DMGs, logs and setup checkpoints.
The root becomes a standalone compressed QCOW2, without an external backing file.

Before packaging, inspect the actual normal-boot screen, record that verification
in the bounded evidence JSON (`visible_springboard_confirmed: true`), stop the guest
and wait for QEMU to exit and flush its disks. Merely pausing the CPU is insufficient.
The evidence must also show this profile, completed patcher, no pending setup,
and no guest panic. The command requires an explicit shutdown acknowledgement.
It does not automatically certify that the operator's visual check was correct.

On the computer with `qemu-img` available:

```sh
python3 tools/vm_bundle.py create /path/to/InfernoDocuments /private/output/Inferno-Machine.zip \
  --proof /private/verified-boot.json --app-commit FULL_40_CHARACTER_SHA \
  --backend-commit FULL_40_CHARACTER_SHA --shutdown-confirmed
python3 tools/vm_bundle.py verify /private/output/Inferno-Machine.zip
```

The tool checks all required state files, records SHA-256 and sizes, checks the
converted QCOW2, verifies the resulting ZIP and refuses to overwrite a bundle.
These checks detect incomplete/corrupted copies; they do not authenticate a
bundle from an unknown source or establish iPhone compatibility.

Keep the output private: it contains guest firmware and state. Never add it to
this public repository, its releases or public workflow artifacts. The ordinary
restore smoke workflow intentionally uploads JSON/PNG only.

The archive is ZIP64 for multi-gigabyte machines. It expands to `InfernoData/`,
`AppleSEPROM-Cebu-B1` and `Machine.json`. On a fresh app, while its VM is stopped,
the intended transfer layout is these files directly inside the app's Documents
folder exposed by Files/file sharing. Do not merge state from two machines or
overwrite an existing machine without a backup. No `automaticSetupPending` or
restore-in-progress checkpoint is carried over. Ordinary launch uses the installed
disk rather than the restore ramdisk. StikDebug JIT is still needed on the iPhone.

**Import/cold boot on the actual iPhone has not been verified.** An in-app archive
import flow and final user instructions must be checked against the actual tested
bundle before delivery; the app's old IPA ZIP reader does not support ZIP64.
