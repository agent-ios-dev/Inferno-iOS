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

Run **39164023616**, app **950c71f**, backend **037ed75**, identified
**dart-usb translation requested during invalidation**. TTBR, invalid page,
unreadable table and protection categories were false. OUT rejected on
`NORData`, 40 seconds; descriptor count=1, index=0, actual=1024, total=32768.
Ownership/buffer/status remained unchanged. Five-second post-error observation
still showed no panic or sequence error. Verification **39164023843 passed**.

Backend **73d8bd1** completes all selected generation invalidations and clears
BUSY before mapping notifier callbacks. Previously notifications occurred
inside BUSY; a reentrant translation was rejected with IOMMU_NONE regardless
of its valid page table. Translation/protection checks remain intact.
New regression compiles the actual invalidation switch case and simulates a
notifier reentering translation, checking BUSY, all selected generations,
SID remapping and empty invalidation sets. Full restore must still validate
this fix; an observed BUSY condition alone did not prove the call stack.
**d1fb886** additionally waits (acquire) for concurrent BUSY completion before
the normal cache lookup/page walk. This is safe only together with **73d8bd1**:
the BUSY region now contains bounded generation atomics and no notifier calls
or operations waiting for a translating thread. The regression also compiles
the actual wait helper and uses a second pthread to complete invalidation;
it has a ten-second timeout to catch deadlock. No permissions are bypassed.
Production remains **37d6816**; no new production IPA was built.

Verification **39164952701 passed** for app **5872064** + backend **d1fb886**:
actual C DMA helper and DART invalidation/wait regression, real Swift USB
socket tests, identity/download validators, iOS/macOS/harness typechecks and
guest daemon C check. Ordering-only regression also passed in **39164811241**.
Clean restore **39165077281**, app **5872064**, backend **d1fb886**, completed
with failure after 275 seconds. Crucially, invalidation was waited for and no
DMA rejection, DART fault, guest panic or mux sequence error was reported.
ASR connected, validated the image and sent fraction **0.0076527** before NAK
timeout. This is progress, not a completed install or confirmed permanent fix.

Next app diagnostic records the exact OUT frame offset/length and buffered IN
bytes at timeout. It also propagates real IN errors during OUT backpressure;
previous `try?` masked them as a later OUT timeout. A real socket regression
now checks this IN error propagation. Keep backend **d1fb886** fixed to isolate
this test. Before a transport rewrite, distinguish timeout before a frame from
timeout midway through it, and check whether IN data is stuck awaiting TCP ACK.
No new production IPA is built; normal guest boot remains untested.

Active timeout-position restore: **39166127705**, app **8fe6e21**, backend
**d1fb886** unchanged. Check this exact run before another restore.
Verification **39165968632** already passed real USB socket tests (including
IN error propagation) and real C DMA/DART tests; platform typechecks were
still running at this checkpoint. Save its final result as well.

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
