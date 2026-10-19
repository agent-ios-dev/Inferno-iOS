# Private candidate retention proposal

This is source preparation, not a deployed private storage destination.
Creation of `agent-ios-dev/Inferno-VM` was rejected by automatic approval review;
specific owner consent is pending in the chat. Do not create that repository or
use another destination to work around the rejection. No guest disks have been
uploaded. The public restore test remains independent of this proposal.

After explicit approval, the proposed private repository would contain this
workflow as `.github/workflows/capture.yml`. It must remain private. The template
checks repository visibility at the job gate, before capture and before artifact
upload. Source and backend inputs require exact full SHA values. Its source
checkout uses the public app repository; it does not copy firmware into Git.

Do not dispatch a duplicate of an already running restore. Inspect the existing
public test first. A private capture run is for retaining the machine for transfer,
once the restore/boot path is established. It uses the actual app and backend,
and captures only after a completed restore and the emulator process has exited.
Root is converted to standalone QCOW2 with normal locking/checking, and all
corresponding SEP/NVRAM/state and boot assets are retained together.

`private-unverified-vm-candidate` artifacts expire after three days. They contain
guest firmware/state and must only go to the approved private destination.
The candidate is deliberately **not** a ready transfer: format0, `Candidate.json`,
explicitly false visual confirmation. `vm_bundle.verify` rejects it. Inspect the
normal-boot screenshot and verify a cold boot before producing the format1 ready
kit with `tools/vm_bundle.py`. Do not relabel a logo or compiled IPA as SpringBoard.

An explicit promotion/private download workflow and iPhone import verification
still need to be completed. This template has not performed a real private capture.
