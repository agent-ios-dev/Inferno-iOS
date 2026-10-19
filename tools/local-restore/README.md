# Local Windows / Docker restore experiment

This prepares and restores a new machine on the owner's PC. These tools are
experimental; a successful build or prepared disk does not establish a working
guest. Do not replace the production backend pin based on this build.

The Docker context is separate from VM storage. It contains `Dockerfile`,
`core.tar` exported from the selected backend commit, and the upstream guide's
`idevicerestore.patch`. Never add firmware, VM disks, tickets or guest logs to
the Docker context or the public repository.

Local paths used in the current experiment, outside this repository:

- `../local-inferno-build`: Docker context and build logs.
- `../local-inferno-vm`: downloaded IPSW, boot files, sparse disks, private logs.
- `../Inferno-guide-source`: original upstream ticket scripts and restore patch.

QEMU is built as a Linux executable with multi-threaded TCG. On an x86 PC,
guest ARM instructions still require translation. This does not use HVF/KVM for
the guest. The iPhone application separately requires its existing StikDebug JIT.

`prepare.py` validates the firmware build, makes the matching tickets/SEP
container and blank disk set. It deliberately refuses existing machine files.
It does **not** install iOS.

`ramdisk_cli.py` generates a temporary Swift CLI from the app's actual HFS+
editor and extracts the two signed guest patchers from the matching IPA. Its
generated source and binaries stay with the local VM. Compile/run it with the
official Swift Linux container; only the resource lookup and Foundation pool
compatibility differ from the app editor.

`run.py --restore` starts QEMU, the Python USB host, and patched idevicerestore.
The resulting private logs stay in `/vm/restore-logs`. Wait for successful restore
**and** the explicit patcher-done marker. Do not hard-kill a writing VM to package
its disks. `run.py` without the flag attaches no restore ramdisk/client and uses
`exit_recovery` for normal boot.

Mount the app and guide sources read-only. Use a writable `/vm` bind mount.
For the running restore, limit the container to 6 CPUs and 6 GiB; publish VNC5900
and QMP4444 / serial5555 on **127.0.0.1 only**, never expose the guest or QMP on the LAN.
Stop the container with a generous grace period (at least90seconds) so the
supervisor can terminate QEMU and flush all disks. Do not run two QEMUs against
the same disks.

After restore: shut down cleanly, retain the original consistent disk set, test
a separate cold copy normally, capture real process IDs and names for both
SpringBoard and backboardd and inspect the guest screen. Only then create the
private transfer with the existing verified-bundle tools. Keep root, SEP,
effaceable and NVRAM together. Never regenerate tickets on an installed machine.

Physical iPhone import/boot still requires separate verification.
