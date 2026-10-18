# Overnight restore investigation — 18/19 October 2026

No completed clean installation, SpringBoard or physical iPhone verification.
Do not promote any current IPA as a working one-button install.

The released-build workflow still pins backend `37d6816`. Nightly tests use
experimental backend `eda00c1` (range-only DMA; no DART bypass, plus two
non-sensitive error classification messages). Its range helper passed a real
C regression test, but the full restore is not validated.

App `c5274ac` changed replay of old usbmux frames to retransmission of only
unacknowledged TCP data in fresh frames. `baa8f13` also bounds IN transactions
to negotiated maxPacket. Run **39160367446** and **39160683584** both failed
with USB IOERROR (-5), before ASR. Neither reported a guest panic or usbmux
sequence error, but this earlier failure is not proof that either is fixed.
Earlier runs reached ASR then panicked with dart-usb PTE-invalid reads.

Run **39161172286** failed on `RootTicket`: OUT endpoint 2, 36 bytes,
USB IOERROR (-5), before ASR, without a reported panic or sequence error.

Completed controlled comparison (same app **5028041**, different exact backend):
- **39162001231**, experimental **eda00c1**: ASR connected and validated image;
  current OUT DMA range failed at 512-byte packet, 80 seconds, fraction 0.00033.
- **39162003162**, shipping **37d6816**: NAK on `NORData`, 170 seconds, before ASR.
Neither reported panic or sequence error; neither completed restore.
Verification **39162001090 passed**. Local bounded evidence is saved in sibling
`smoke-evidence-<run>` directories.

Backend **bc6ce84** adds diagnostic classifications for reset, guest ENDXFER,
queued NAK and inflight dispatch NAK (no behavior change). The smoke report
exports fixed booleans for these paths, not raw USB/firmware data. This backend
has not yet been built or tested; production remains pinned to **37d6816**.
It additionally distinguishes address-space rejection from scatter-list
exhaustion. The next restore should use this exact backend to classify the
observed OUT failure before changing transfer semantics again.
Reports also include `current_dma_in_failed` / `current_dma_out_failed`.

Verification on `ff5ca7c`: **39160921179 passed** (real Swift download validators,
real USB transport socket tests, actual backend DMA helper tests, shared source
typechecks and guest C syntax check). Check the newest verification as well.

Evidence artifacts: `restore-smoke-evidence` contains bounded JSON and actual
guest framebuffer PNG. Only an inspected real UI can confirm graphical boot.
The harness observes 900 seconds after successful restore/reset, never labels
a received image as SpringBoard automatically, and keeps private raw logs and
guest firmware/disks off GitHub artifacts.

Local checkouts: sibling folders `Inferno-iOS` and `Inferno-core`. No input
from the user is presently required. Nightly continuation is attached to this
chat every 15 minutes until 09:00 Moscow on 19 October 2026.
