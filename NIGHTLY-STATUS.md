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

Active at this checkpoint: **39161172286**, app `ff5ca7c`, backend `503a4c2`.
Its JSON adds `last_restore_request`; the displayed error includes token,
endpoint and packet length. Inspect its actual result before dispatching a
replacement. Current main additionally pins `eda00c1` for the next smoke run
and reports `current_dma_in_failed` / `current_dma_out_failed`, which distinguish
our range helper's IOERROR from DWC3 cancellation paths.

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
