# Overnight restore investigation — 18/19 October 2026

## Deadline checkpoint — 19 October 2026, 06:00 UTC / 09:00 Moscow

Nightly automation `podium7` was deleted through the app at the requested
morning deadline. No verified SpringBoard, completed clean restore or physical
iPhone launch. No new IPA is presented as working.

Latest active full restore: **39203613722**, app **f933ace**, backend
**d5dcc2f0a353f65d9be4ba7b4d4011887f4c2f67**. At the final check it remained
in progress; its last visible stage at 05:58 UTC was **System image 30%**.
Do not start another identical test: first obtain this run's final bounded
`restore-smoke-evidence` JSON/PNG. The existing finite CI job is left to finish;
no recurring continuation remains scheduled. It can terminate on NAK or its
6300-second application budget. An unfinished run is not a successful restore.

Verification **39203613158 passed**: actual transport socket regressions,
actual DMA/DART helper regressions, iOS/macOS/harness typechecks and guest
patcher syntax check. Native test emulator and actual Mac restore app built.
These checks do not establish a working guest UI or physical-device JIT.

Last completed restore **39201121932** failed after 905 seconds at ASR9.27%,
NAK frame byte0/16383, IN buffered0. ASR TCP window114688/inflight0/open,
no guest panic, checksum/mux or DART access failure in bounded report. Precise
controller refusal branch remains unconfirmed until current test completes.
Its new report samples reason1 disabled,2 no transfer,3 no descriptor,4 copy
path, with first-descriptor counters and pending-event bytes; last8 snapshots
only, no addresses/firmware/payload/raw guest logs. A previous one-off sample
showed enabled ep4/active transfer/3 buffers/pending0, but its timing cannot
be tied to the final failure, so it is not proof of queue corruption.

Next work: inspect current run's final snapshot before selecting a controller
fix. If restore completes, require patcher done, successful reset to ordinary
boot, and visual framebuffer inspection before claiming SpringBoard. Shipping
workflow still pins **37d68169800a2e41de7da7e96478a15ac4431ca7** (verified).
All experiments remain unpromoted. Earlier reports and changes are retained
below; latest diagnostic reports are committed under `reports/2026-10-19-*`.


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

ASR graceful-close restore **39188070550**, app **e69acff**, backend **d1fb886**
failed after 3025 seconds: full payload sent, then guest went away while
waiting for ASR close acknowledgement. No restored FIN/RST, no DART/panic,
FUD not yet reached. Verification **39187942272 passed**.

Next app allows ASR peer close *after the complete payload only* to return to
the restored protocol loop. It does not call it successful delivery or restore;
restored progress/error/final StatusMsg remains authoritative. Other finish
errors still fail. A graceful FIN still must be acknowledged, and report
distinguishes peer close from acknowledged FIN. TCP close logs bounded port
and outstanding byte count. Socket test also checks peer RST is surfaced as
gone, never mislabeled acknowledged FIN. Keep backend **d1fb886** fixed.

The new RST socket regression initially failed (**39192548420**): serviceMux
kept polling after marking a channel reset instead of returning that handled
event. App **bb0baf1** returns immediately after RST. Verification
**39192720987 passed** all socket tests, real C DMA/DART tests, iOS/macOS and
harness typechecks, guest daemon check. Active full restore **39192852048**,
exact app **bb0baf1**, backend **d1fb886**. Do not duplicate this run.

Update: **39192852048 failed** at 745 seconds, ASR fraction 0.080214,
OUT NAK offset 0/16383, IN buffered 0. No DART/panic/mux error, FUD not reached.

App **f1c6fa7** changes the serialization model, rather than restoring the
rejected ACK queue. serviceMux first owns sendLock, then serviceLock, matching
writers; TCP txSeq/pending bytes publish after the actual frame send while
that common gate is still held. A NAK at frame byte zero may service a whole
buffered incoming mux frame (with the reserved mux number handed back), then
rebuild the unsent frame header. A partial frame is never interrupted/replayed.
Nested pure ACK uses the old *transmitted* TCP sequence, not the future data
sequence. New real socket test checks incoming byte -> ACK sequence 0, ack 2,
mux 0 -> unchanged payload under mux 1 and final data seq 100.
Regression step passed in **39194983695**, full typechecks still pending.
Backend remains **d1fb886**; shipping IPA **37d6816**, no release promotion.

Active serialized-transport restore **39195127679**, app **f1c6fa7**, backend
**d1fb886**. Inspect this result and final verification **39194983695** before
dispatching a replacement. Do not duplicate the active test.

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

04:43 UTC: restore **39195127679 failed**, app **f1c6fa7**, backend
**d1fb886**, at fraction 0.489443 / 3775 seconds. OUT NAK at frame byte
0/16383, buffered IN 0. ASR validated but payload incomplete. No guest panic,
DART access fault, checksum failure or mux sequence error. Patcher remains
waiting; data volume absent. Verification **39194983695 passed** completely.
The new serialization has NOT fixed restoration; no production promotion.

Next diagnostic backend **e18bd7b** adds only a saturating per-endpoint OUT
NAK counter: once per 1024 consecutive refusals, records endpoint enabled,
transfer present, descriptor count, can-free, control phase, event mask and
pending event byte count. It changes no events, ownership, DMA, retry or
completion behavior. Host timeout records fixed TCP window/inflight/inbox
counters. Harness exports at most eight numeric snapshots per category; no
addresses, payload, firmware or raw guest logs. This distinguishes missing
transfer resources from disabled endpoints or undrained completion events,
before making another behavioral change. Shipping backend stays **37d6816**.

Active diagnostic restore **39201121932**, exact app **b3c3261**, backend
**e18bd7b0f0ac519cced473fc9772a344193828e2**. Verification **39201122368**
is running; inspect both before replacing this run. No duplicate dispatch.
At 04:51 UTC backend build has started. The preceding PNG was inspected:
Apple logo with incomplete restore progress bar, no SpringBoard. This run
adds observability, not a claimed behavioral fix. At the 06:00 UTC deadline
preserve its actual state if it has not completed and stop the nightly schedule.

05:13 UTC: **39201121932 failed** after 905 seconds at ASR 0.092748.
No panic, DART access fault, checksum/mux error, FUD or patcher readiness.
Verification **39201122368 passed**. Timeout TCP snapshot: ASR window114688,
inflight0, inbox0, open; restored window131072/inflight0, open. Thus the final
stall does not show an unacknowledged TCP window blocking the ASR writer.
One controller snapshot: OUT ep4, enabled1, transfer1, buffers3, can_free0,
control0, eventmask6, pending0. Its timing is not known: the old 1024-poll
threshold could miss slow retries at the final stall; do not assert queue
corruption from that earlier sample.

Next backend **d5dcc2f** records the precise NAK branch (1 disabled endpoint,
2 no transfer, 3 empty descriptor queue, 4 copy/status path) and first descriptor
presence/count/actual/total, consecutive NAK count, at most every5 seconds.
Only numeric metadata; no addresses or payload, no completion/event behavior
changes. Harness retains last8 snapshots, so evidence covers the final stall.
Keep shipping backend **37d6816**. No full restore/SpringBoard confirmed.

Active branch-classification restore **39203613722**, app **f933ace**, backend
**d5dcc2f0a353f65d9be4ba7b4d4011887f4c2f67**. Verification **39203613158**
is pending/running as of05:15UTC. Do not duplicate. Last completed diagnostic
restore is **39201121932**; its bounded JSON is committed above. At the deadline
stop the nightly schedule and preserve exact remaining blocker/run state.

## Resumed by user after morning deadline

User requests continued work until actual SpringBoard, then a complete VM
transfer file so the iPhone skips restoration. Do not publicly publish guest
images, firmware or private state; deliver a verified consistent machine via
an appropriate private/local export after a clean shutdown. Preserve all SEP,
NVRAM and device-state disks together, not root alone. No working image yet.

**39203613722 completed with execution-budget exhaustion**, not OUT timeout:
6300 seconds, System image fraction **0.921757**, machine still running. No
reported panic, DART access error or mux/checksum error. Last8 NAK samples
show reason3 empty descriptor queue, enabled ep4, active transfer, zero buffers,
NAK count1 and pending4/8. These are intermittent resource gaps that recovered,
not evidence of the terminal 60-second NAK observed in older runs. Early ASR
flags have scrolled out of the bounded host log (false in final old JSON does
not mean ASR did not start; actual progress reached92%).

Next test holds runtime app and backend **d5dcc2f** unchanged, increases
harness budget to10800 seconds and workflow to210min to permit full transfer,
patching/reset and900sec normal-boot observation. Harness now retains fixed
ASR/restored event flags across log rotation, never raw logs. This changes
test observation only; no fabricated success or promoted production backend.

Active extended-budget restore **39237004400**, app **a2a81f2**, backend
**d5dcc2f0a353f65d9be4ba7b4d4011887f4c2f67**. Verification **39237004346**
passed socket/DMA/DART steps; platform typechecks still running at checkpoint.
Do not duplicate. Continuation automation **inferno-springboard-vm** is active
in this chat every15min, no morning deadline, until verified UI plus private
VM transfer bundle and matching IPA. It replaces the deleted nightly schedule.
The current public diagnostic workflow still exports JSON/PNG only; it does
not retain or deliver guest disks. Once UI is proved, prepare/verify the full
transfer via a private/local route, not by adding raw disks to public artifacts.

Transfer tooling **e734140**: `tools/vm_bundle.py` creates a local/private
standalone QCOW2+ZIP64 machine kit, selected boot files and all SEP/NVRAM/state
disks together; SHA256/size manifest and exclusive atomic final publication.
Requires explicit stopped-machine acknowledgement and actual confirmed boot
proof; refuses incomplete proof/overwrite. No raw guest disk was uploaded.
`VM-TRANSFER.md` records current limits: no verified guest kit, in-app archive
import still absent; ZIP64 requires Files/external extraction for now. Do not
present the packer as a running machine or as verified iPhone import.
Verification **39238827700 passed**, all9 synthetic-fixture packaging tests on
Mac including real qemu-img convert/check/no backing-file, plus existing actual
USB/DMA/DART checks, iOS/macOS/harness typechecks. Locally Windows passed7,
skipped symlink privilege and unavailable qemu-img; CI ran all9 without skips.
Public restore **39237004400** remains active, last visible System image10%.
It still tests app **a2a81f2**, unchanged backend **d5dcc2f**; no duplicate run.
