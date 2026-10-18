# Overnight restore investigation — 18/19 October 2026

No completed clean installation, SpringBoard or physical iPhone verification.
Do not promote any current IPA as a working one-button install.

The released-build workflow still pins backend `37d6816`. Nightly tests use
experimental range-only DMA (no DART bypass). Its helper passed a real C
regression test, but the full restore is not validated.

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

Run **39162736532**, app **c0c8d34**, backend **bc6ce84**, failed after ASR
validation at 150 seconds: **address space rejected current OUT DMA range**.
Scatter-list exhaustion, controller reset, guest ENDXFER, queued/inflight NAK
classifications were all false. No reported panic or sequence error.
Verification **39162736698 passed**. This narrows the failure to DMA translation,
not the cancellation paths. Sanitized reports are committed under
`reports/2026-10-18/`; no guest data or raw logs are included.

Run **39163372932**, app **ee8d1d6**, backend **06010cc**, failed on `NORData`
at 120 seconds: current OUT DMA rejected, descriptor metadata readable,
ownership still HWO, buffer/status unchanged. No cancellation classifications,
no reported panic or sequence error. This run does not support the hypothesis
of a reused/unowned descriptor. Verification **39163372686 passed**.

Next backend **037ed75** classifies dart-usb faults (TTBR, table read, invalid
page, protection, invalidation busy) using fixed strings only. No fault is
bypassed. The harness now waits five seconds after setup failure before
collecting evidence, to let a possible fault interrupt/panic reach the console;
it also exports four bounded descriptor counters, never addresses or payloads.
Production remains **37d6816**. Inspect the next run before changing DMA or
USB semantics; current evidence calls for translation-level diagnosis.

Active at checkpoint: **39164023616**, app **950c71f**, backend **037ed75**.
This is the DART classification + five-second fault observation test. Check
its actual report and verification on the same app revision before scheduling
a new restore. No duplicate run is needed. No production IPA was built.

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
