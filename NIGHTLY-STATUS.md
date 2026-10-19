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

Completed restore **39166127705**, app **8fe6e21**, backend **d1fb886**:
failed after 5250 seconds on patcher deadline, with **Halt/Restart Timed Out**
kernel panic. No patcher-done marker or normal system boot confirmed.
Verification **39165968632 passed**, including real USB socket tests (IN error
propagation), real C DMA/DART tests and platform typechecks.

Live Actions inspection at **21:59 UTC**: **39166127705** is still running,
but it has progressed through System image 95%, System 100%, Installing 100%,
Device tree, and now **Filesystem patches 95%**. Do not cancel or duplicate
this run while the existing one-hour patcher deadline is still active.
This is not yet a completed restore/reset or a booted SpringBoard.
The next harness revision adds fixed patcher-phase booleans to its final
report (waiting, data ready, mount, cache patch start/exit, failed/done),
without publishing patch addresses or raw console lines. This revision does
not affect the already-running restore; inspect its actual result first.

Update 22:44 UTC: that run is now complete. Actual public progress timestamps:
image 95% at 21:29, System 100% at 21:31, Installing 100% at 21:33, patcher
wait at 21:35, timeout at 22:35. Final ASR flags are false because the bounded
host-log tail lost earlier entries, not because image transfer did not happen.
Verification **39170290111 passed** for the patcher-phase report additions.

Next harness streams and retains fixed guest phase flags every five seconds,
independent of final-tail truncation. This tests whether the daemon started,
saw data, mounted, patched or exited before reboot timeout; only fixed phase
names leave CI. RestoreSession now fails on a panic seen while waiting for
the patcher rather than wasting a full hour. Keep backend **d1fb886** for
this comparison. Do not bypass the reboot panic or claim patched boot.

Run **39173701228**, app **22dcfee**, backend **d1fb886**, failed at 2020
seconds with "guest went away", last request **FUDData**. Full ASR payload
and validation are confirmed in JSON. Only observed patcher phase is
**waiting**; data volume readiness/mount/patch were never observed. No DART
fault/panic/mux sequence error reported. System 100% at 23:22 UTC, Installing
100% 23:23, channel lost 23:24. Verification **39173607983 passed**.

Next diagnostic adds a fixed seven-bit guest volume-presence mask while the
daemon waits: bits 0..6 = disk0, disk0s1, disk0s1s1, disk0s1s2, disk1,
disk1s1, disk1s2 under /dev. No contents/addresses are exported. This will
distinguish wrong hardcoded volume numbering from a genuinely missing data
volume. Host also classifies restored port FIN vs RST. Do not treat a closed
channel as restore success or change volume paths until evidence supports it.
Backend stays **d1fb886**, shipping IPA still **37d6816**.

Volume-mask restore **39176850488**, app **9a01fe2**, backend **d1fb886**:
failed after 3695 seconds, **restored channel RST confirmed**, FIN false,
last request **FUDData**. Full ASR payload confirmed, no DART fault/panic/mux
sequence error. Daemon remained in waiting. Volume masks 1,17,19,23: disk0,
disk0s1, **disk0s1s1 system exists**, disk1; **disk0s1s2 data absent**. No
disk1s1/s2 observed. Thus no evidence for changing hardcoded volume paths.
Verification **39176753029 passed**.

Compared `imageData` with libimobiledevice/idevicerestore's real
`restore_send_image_data` implementation: list/single/all reply shape matches.
Do not invent a protocol-shape fix. Next app adds bounded FUD metadata events:
request component name + list flag, prepared, sent. No component payload,
ticket or key is exported. This locates RST during preparation vs sending vs
waiting for the next request, and identifies which FUD request is implicated.
Backend remains **d1fb886**, no new production IPA.

FUD-phase restore **39182272475**, app **6e2038e**, backend **d1fb886**,
failed earlier during ASR at fraction **0.279692**, 640 seconds: OUT NAK
timeout, **frame offset 0/16326, buffered IN 0**. No byte of this frame
was accepted; no DART fault, panic, sequence error or restored FIN/RST.
No FUD request reached. Verification **39182174648 passed**.

Next app increases finite zero-consumption NAK patience from 60 to 180 seconds.
No positive partial transfer is retried, no success is fabricated, byte-count
checks remain strict. This tests a slow translated guest's descriptor repost
delay; it is not evidence that the eventual FUD reset is fixed. Keep existing
FUD diagnostics and backend **d1fb886** for the next full restore.

Bounded-patience restore **39184436917**, app **7c6618e**, backend **d1fb886**
failed at ASR fraction 0.314829, 1025 seconds: same frame offset 0/16326,
buffered IN 0. Three-minute timeout did not solve it; patience reverted to 60.
No DART/panic/mux sequence error, no FUD reached. **39184423393 passed**.

App **607bdbd** tests a concrete reader/writer lock inversion: serviceMux used
to hold a received ACK while blocking on sendLock, while the writer waited
for guest capacity. ACKs now queue/coalesce without blocking the reader;
a fully unaccepted frame can give its mux number to the ACK, then rebuild
its own header with the next number. Never inserts an ACK midway through an
accepted frame. Pending same-channel data uses its unsent TCP sequence for
the intervening ACK; no bytes are replayed. Socket regression reproduces the
NAK-until-ACK peer and checks mux 0 ACK -> mux 1 original payload. It passed
in **39186853764**; platform typechecks were still running at this checkpoint.
This does not yet establish the cause of the real guest's NAK or FUD RST.
Production IPA still pins **37d6816**; do not promote the experiment yet.

ACK-priority restore **39186986002**, app **607bdbd**, backend **d1fb886**
failed much earlier at 90 seconds, restored RST on NORData before ASR. Tests
**39186853764 passed**, but runtime regressed. **ACK-priority experiment is
removed from GuestUSB and its test**; use the pre-experiment transport as base.

Next concrete issue from source: ASR's final `channel.close()` sent RST even
with unacknowledged TCP bytes (USB acceptance is not delivery). Existing
netlab/muxd.py explicitly drains and FINs ASR for the same reason. New `finish`
waits for data ACK, sends FIN|ACK, waits for FIN ACK and removes the channel
without RST. FIN consumes sequence space and guest FIN is acknowledged.
RestoreClient uses this on successful full ASR transfer; error paths keep RST.
Socket test requires data ACK before FIN, verifies FIN sequence/flags, then
FIN ACK and no extra RST. Report adds `asr_payload_and_fin_acknowledged`.
This is not yet runtime validated. Backend stays **d1fb886**, IPA **37d6816**.

Active ASR graceful-close restore **39188070550**, app **e69acff**, backend
**d1fb886**. Verification **39187942272** passed socket tests (including
data-ACK -> FIN -> FIN-ACK -> no RST); typechecks still running at checkpoint.
Inspect these results before a replacement; do not duplicate this restore.

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
