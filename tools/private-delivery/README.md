# Private candidate retention proposal

The owner explicitly approved `agent-ios-dev/Inferno-VM` and private Actions
artifacts on19October2026. That repository has been created, verified private,
and provisioned with the manual capture workflow. No real capture has been
dispatched yet and no guest disks have been uploaded. The earlier automatic
approval rejection was resolved by that specific consent; do not assume consent
for a different storage destination. The public restore remains independent.

The private repository uses this workflow as `.github/workflows/capture.yml`.
It must remain private. The template
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

After retaining the candidate, the workflow stages its checked archive into a
new Documents folder, with no setup downloads or restore checkpoint. A second
app invocation uses `INFERNO_SMOKE_MODE=cold-boot`: normal `VMModel.start()`,
no call to AutomaticSetup and no restore ramdisk. It observes for15minutes after
startup (30minute limit) and exports bounded JSON/PNG separately. A frame still
requires visual inspection; automatic success never claims SpringBoard.
The original captured archive remains unchanged if this cold boot fails.
