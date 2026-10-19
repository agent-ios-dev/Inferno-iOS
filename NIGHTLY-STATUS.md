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

Private delivery provisioning is awaiting an explicit user answer. Auto-review
rejected creation of a new `agent-ios-dev/Inferno-VM` private repository/local
checkout: general project permission did not explicitly cover that new storage
destination for guest disks. No repo was created, no disk uploaded. A targeted
async question is pending: allow that private repo and private Actions artifacts,
or keep the kit local only. Do not retry/re-route around that rejection without
specific consent. This does not block the active public JSON/PNG-only restore.
The active CLI watcher is session59928 (gh run watch39237004400), redirects
routine status to local work/restore-watch-39237004400.txt. Keep waiting for its
actual result; do not treat pending private storage consent as a boot blocker.

Private-retention preparation **e7091d4** is source-only inside the existing
approved app repo, not a newly created repo or deployed workflow. Template
`tools/private-delivery/capture.yml` gates on private visibility, rechecks before
capture/upload, uses immutable source refs and retains candidate artifacts3days.
`capture_candidate.py` requires completed restoration and an exited emulator;
it saves standalone QCOW2 + all consistent state as format0/Candidate.json,
explicitly UNVERIFIED. Ready-kit verifier rejects it. Promotion and actual
private deployment remain outstanding and require the pending specific consent.
No actual private VM capture occurred, no new restore dispatched.
Verification **39244791312 passed**: all11 synthetic-fixture tests on Mac,
including real qemu-img conversion for both ready-kit/candidate paths, incomplete
restore rejection and rejection of a candidate as a ready kit; private template
YAML parsed. Existing transport/DMA/DART/platform checks passed too. Local
Windows passed8, skipped3 unavailable qemu-img/symlink tests. Runtime `app/`
is byte-for-byte unchanged from active full restore **a2a81f2** (`git diff` checked).

Host acceleration evidence: **39245428919 passed** the initial signed native
HVF capability probe and all existing checks. Requested40-bit IPA configuration
returned4209590287. Do not infer default VM support from that setting alone.
Improved probe **3cc9c07**, run **39245757011**, separately attempts default
VM creation and names the actual SDK status. Its already uploaded bounded JSON
shows **HV_UNSUPPORTED** at both configure_ipa40 and default vm_create. No
firmware, RAM or guest instructions ran in the probe. On these hosted runners
HVF cannot accelerate restoration; don't switch to it on an assumption.
Full verification39245757011 still running at this checkpoint; inspect final.
Active restore39237004400 reached System image60%, no duplicate dispatched.

Specific storage consent is now resolved: the user explicitly approved private
`agent-ios-dev/Inferno-VM` and its VM disk Actions artifacts. The repository was
created and verified private; checkout `work/Inferno-VM`, main **6292821**.
Its capture workflow is provisioned and active but has NOT been dispatched.
The earlier automatic-review rejection no longer blocks this approved destination.
No guest disk has been uploaded. Do not use a different destination implicitly.

App **4928802**, verification **39246903205 passed**: all12 packaging tests
on Mac with real qemu-img, template YAML, USB/DMA/DART and shared platform/harness
typechecks. Candidate/ready proof now requires a live guest and frame and rejects
persisted panic observations. Private capture may observe up to14400seconds;
ordinary restore default remains10800. Runtime app sources remain unchanged from
the active a2a81f2 run. HVF probe verification39245757011 also completed successfully;
its report still says HV_UNSUPPORTED, not available acceleration.
At14:48 Moscow active restore **39237004400** is at System image65%; continue
watcher59928 and inspect its real result. No second full restore was started.
Next delivery work is a clean normal cold-boot check of the retained closed VM,
plus verified import; neither packaging checks nor an unverified candidate is UI proof.

Cold-boot preparation **794ff62**, checks **39247553271 passed**:15 synthetic
packaging/staging tests on Mac, including actual qemu-img, safe new-folder
extraction/hash checks/no merge/no restore checkpoint, plus all platform checks.
App **cb24054a95e42f79983c33d41f1774dd9b4c6a87**, checks **39248011255 passed**,
adds bounded read-only live `pgrep -x` evidence for SpringBoard/backboardd during
the separate cold boot (strict PID/name parser tested; no guessing from logs).
Private workflow updated to **360f600**: captures original closed VM first,
uploads private UNVERIFIED candidate, stages separate QCOW2+state copy, invokes
normal VMModel.start with no AutomaticSetup/restore ramdisk, observes15minutes,
exports JSON/PNG for actual inspection. Candidate is not promoted automatically.
No private restore/capture dispatched yet. Main restore39237004400 unchanged.
User asked about doing restore on the local PC, then explicitly chose to leave
the current Mac approach as it is. Read-only inventory: Ryzen7 4800H x64,
16GB RAM, approximately125GiB free on C, no installed WSL distribution and no
local QEMU build. Do not install a local toolchain as part of that question.

Restore **39237004400 FAILED** after5410seconds, appa2a81f2/backendd5dcc2f.
Bounded report `reports/2026-10-19-39237004400-empty-out-queue.json`:
OUT NAK timeout frame0/16326, no bufferedIN. Enabled ep4 with active transfer,
zero descriptors, can_free0, eventmask6 and pending0 throughout last8samples;
consecutive NAKs15531..19398. ASR channel still open with16347bytes in flight,
window114688; restored open/inflight0. No DART invalid/protection/read error,
no DMA copy error, no panic/mux sequence/checksum failure. Patcher only waiting,
ASR not completed, screenshot visually inspected: Apple logo + partial progress.
Neither SpringBoard nor backboardd proved. Watcher59928 completed with exit1.

Backend candidate **1ec087f2746bbd23f18cc1ae1736451a27e11ed3** fixes two
independently demonstrable false TRB-loop conditions: reversed queued-descriptor
upper bound and overbroad count+1 self interval. Links now match actual populated
TRB addresses. Real cycles remain stopped. Adds bounded fetch-stop reason to
existing NAK diagnostic, no extra DMA reads. Regression test extracts/runs actual
dwc3_td_fetch and checks adjacent/ascending links, real cycles and HWO; baseline
d5 is a negative control. CI verification pending; do not claim this caused the
observed stall or promote to production yet. No duplicate full restore active.

Verification **39249074324 PASSED** for app **f0142f66d7c97f1510025128b349deb8b6620374**:
actual TRB fetch tests accepted adjacent/ascending chains, stopped real cycles,
respected HWO; the original d5 backend FAILED the negative control as expected.
DMA/DART/socket checks,15 packaging/staging tests, PID parser and both platform/
harness typechecks passed. This proves the code defect/regression, not guest UI.

One new full restore was dispatched to approved private **Inferno-VM**:
**39249482181**, workflow **360f6006cb82f6416de46489cf3e597d2337494b**,
app **f0142f66d7c97f1510025128b349deb8b6620374**, backend
**1ec087f2746bbd23f18cc1ae1736451a27e11ed3**. Currently queued at15:07Moscow.
Do not duplicate. It builds the actual Mac library, restores from no files,
retains a closed candidate privately only after completion, then cold-boots a
separate verified copy without restoring again. Inspect both JSON/PNG outputs;
no automatic SpringBoard claim. Native build/real restore still pending; iPhone
library builds and real device import remain unverified, production pin37 unchanged.

While that comparison builds/runs, inspection found an additional independently
testable fetch defect: dwc3_bd_length's negative count prematurely set the outer
`ended` flag before the inner do/while, so a terminal descriptor with multiple
owned TRBs loaded only its first. This can omit LST/IOC-bearing trailing entries;
it is consistent with empty active queue/can_free0/pending0 but not yet proved to
be the real guest's stall. Backend **b533085982f346a954b4ce8e27a827b04d64b3ce**
lets actual LST/HWO checks end fetching after the whole owned descriptor. Tests
now cover multi-TRB terminal LST and HWO boundary, with 1ec087f as a separate
negative control. Verification pending. No second concurrent restore dispatched.

## USER-REQUESTED PAUSE — 19 October 2026, 15:16 Moscow

User is restarting Codex and explicitly requested a pause. Do not start work or
dispatch another run until the user resumes. Automation `inferno-springboard-vm`
is confirmed **PAUSED** by automation_update. No running guest test remains:
private run **39249482181** is confirmed **completed/cancelled**. Its original
native Mac library/app build passed; it was cancelled to replace the independently
reproduced terminal-TRB defect, not evidence of successful restore. No candidate
disk/ready VM/working SpringBoard was produced. No replacement run was started.

Latest verified runtime/test source app **10ef170939c0abbfbc73e29291fc843719d5e3e3**;
backend **b533085982f346a954b4ce8e27a827b04d64b3ce**. Verification
**39250089772 PASSED**, including actual complete terminal descriptor fetch,
adjacent/ascending links, genuine loop stopping and ownership. Both earlier
backends failed negative controls; DMA/DART/socket,15 transfer tests and shared
iOS/macOS/harness checks passed. This is NOT real-restore or UI verification.
Private workflow **360f6006cb82f6416de46489cf3e597d2337494b** remains provisioned
in approved private Inferno-VM; main workflow input backend must be explicitly
overridden, because its default is older d5. Production IPA still pins37d6816.

After explicit resume: inspect actual Actions first; then dispatch exactly one
private capture.yml with app_ref10ef170939c0abbfbc73e29291fc843719d5e3e3 and
emulator_refb533085982f346a954b4ce8e27a827b04d64b3ce, unless newer evidence
requires a change. It builds the native library, restores, retains only a closed
completed candidate, then starts a separate cold copy normally (no restore).
Inspect bounded JSON/PNG and actual screen; require real SpringBoard/backboardd.
iPhone library builds/import and actual iPhone boot still need verification.
Never publish firmware/disks/keys/raw guest logs in public repositories/artifacts.
Worktrees are saved; only this checkpoint is newer than the last verified app SHA.

## RESUMED — 19 October 2026, 15:20 Moscow

User explicitly said continue after restart. Work is active again; automation
inferno-springboard-vm is ACTIVE with refreshed checkpoint. No other active private
run was present. Exactly one private restore **39251197224** dispatched:
app **10ef170939c0abbfbc73e29291fc843719d5e3e3**, backend
**b533085982f346a954b4ce8e27a827b04d64b3ce**, workflow **360f600**.
Repo rechecked private. Watcher session83242 redirects routine state to
work/private-watch-39251197224.txt. Inspect this run, do not duplicate it.
All three worktrees were clean at resume. Old production backend remains pinned.

At15:33Moscow the resumed native library/app builds passed and actual ASR image
transfer reached5%. Still no normal UI evidence. A proposed early iPhone IPA
compile dispatch was REJECTED by automatic approval review: IPA build must wait
for the user's prerequisite of real restore and SpringBoard/backboardd/UI proof.
Nothing in that command executed. Do not retry an early IPA build or route around
the rejection through an equivalent workflow. This does not affect the running
private restore39251197224; continue it. No early IPA was built or delivered.

At15:45Moscow private restore39251197224 remains active and System image10%.
Do not dispatch another. Clarified verification workflow name/run-name to
`Code checks only — guest iOS is not booted`, because commit title mentioning
SpringBoard/backboardd confused the owner into interpreting green checks as
actual guest process evidence. Metadata only; no runtime behavior changed,
no redundant verification run requested. Historical run titles remain historical.

User now EXPLICITLY requested the IPA of the revision currently being tested,
before SpringBoard proof. This supersedes the earlier inferred build-order
restriction for this experimental IPA only; never label it working iOS.
Exact app10ef170939c0abbfbc73e29291fc843719d5e3e3/backendb533085982f346a954b4ce8e27a827b04d64b3ce.
GitHub workflow dispatch rejected a raw SHA ref (422), so an exact branch
`build/current-10ef170-b533085` was created at that SHA, then IPA build
**39257092574** dispatched successfully. No substitute runtime or production pin
change. Await build, download actual Inferno-ipa artifact, check IPA contents and
give the file with explicit unverified-SpringBoard status. Main private restore
39251197224 continues separately; no duplicate restore. Watcher83242 is the
original private run watch; outer exec38 was stopped, not the GitHub restore.

Experimental IPA build **39257092574 SUCCEEDED**, exact app10ef170/backendb533085.
Downloaded local `work/ipa-39257092574/Inferno.ipa`,7536905bytes,
SHA256 b58ccd9cb491f7edad4a92de806d4bcefecd6774e464617c049af16af759a15b.
Checked ZIP CRC, bundle ID dev.agent-ios.inferno, app+dylib arm64 iPhoneOS targets,
get-task-allow entitlement, both required guest patchers, expected backend
diagnostic string. Bounded verification report committed in reports/. This is
NOT physical iPhone testing or SpringBoard proof. User explicitly requested this
experimental IPA now; provide local file. Production workflow default unchanged.
Private restore39251197224 remains active; last observed system image25%.

At16:45Moscow current run39251197224 still active, visible image35% unchanged
since at least16:28. Browser reloaded to exclude stale UI; still35%. Do not infer
healthy progress from a running job. Current runner cannot receive new code.
Job-log API returned only completed build logs through12:20UTC, not the active
restore's internal logs. Those local private files were NOT published. No
candidate/diagnostic artifacts yet. Await actual final report before causal claims.

Preparing host-only stall diagnostics for a FUTURE run, without duplicating or
cancelling this restore: test harness writes atomic bounded progress timestamps;
watchdog samples the explicit fresh test process after600seconds without actual
fraction/message progress, at most3 times. Only fixed known host function-name
counts are exported. Raw sample/address/path/arguments stay in deleted temporary
local storage; never guest memory or raw logs. Python privacy test passed locally,
native Mac sample check and Swift harness typecheck pending in CI. Runtime app/
and backend remain unchanged, delivered IPA still matches the current restore.

Watchdog verification **39263989160 PASSED**, app diagnostics source
**ddd6fb883bc6d8e2c0726757b083392d186eac9d**: real native sample of own Mac child
returned exit0 (not merely parser fixtures), privacy checks and Swift harness/
platform checks passed. Prior superseded check39263886672 was cancelled to avoid
duplicate checks; initial39263288815 passed. Runtime `app/` diff from10ef170 is0.
Fixed bounded counters are printed in LIVE Actions output, not just final artifacts.

At16:57Moscow requested cancellation of **39251197224**, after image35% bucket
unchanged for at least29minutes. This is NOT proof of deadlock or of the cause;
the old harness exposes no fine-grained progress/host stacks. Bounded observation
saved in reports/2026-10-19-39251197224-progress-observation.json. No VM was claimed
restored or retained. Replacement will run the same runtime/backend, adding
progress-aware stack observation to avoid another blind multi-hour wait.
Private workflow **e7b4963** now contains watchdog wrapper. Wait for old run to
finish cancelling BEFORE dispatching one capture with app_refddd6fb883bc6d8e2c0726757b083392d186eac9d,
backendb533085982f346a954b4ce8e27a827b04d64b3ce. Do not duplicate active restores.

Old39251197224 confirmed completed/cancelled before replacement. New single
private restore **39265025275** queued at17:00Moscow, exact app diagnostics
**ddd6fb883bc6d8e2c0726757b083392d186eac9d**, backend **b533085982f346a954b4ce8e27a827b04d64b3ce**,
private workflow **e7b4963**. No runtime app/backend change from the user IPA;
extra diagnostics only. Watcher **74334**, file work/private-watch-39265025275.txt.
Automation refreshed to this run. Watch LIVE `Host stall diagnostic` if progress
stalls: bounded known host symbols only. Never interpret sample_exit0 as boot.

## Local PC restart checkpoint
After the user rebooted, Docker Linux engine is stopped. IPSW partial download remains intact at 1589861354 bytes; expected full size 5507405643. Local Docker build had failed before reboot on missing liblz4. Added liblz4-dev to local-restore Dockerfile; rebuild not yet run. Attempt to restart Docker and resume Apple download was blocked by execution policy; no retry through another route. No installed local VM or SpringBoard proof exists. Resume from partial download and cached Docker layers once execution is available.


## Local PC resumed after reboot — 19 October 2026
Docker Linux is live. Apple IPSW download completed, exact5507405643bytes; full ZIP CRC passed and manifest18A5351d / exactly one n104ap Erase identity verified. Local QEMU b533085 compiled successfully (standalone x86_64 Linux, TCG). Archive scripts had CRLF shebangs; build-only normalization fixes execution without runtime source edits. liblz4-dev added. Official idevicerestore patch also needed LF normalization; source pinned4b3e847e1d9a1210049a9e3f1d1caa38650c6617; native build passed. Docker image exporting. Swift6.2 Linux RAM-disk CLI built successfully using actual app HFS+ source plus resource/pool compatibility shim and both guest patchers extracted from experimental IPA39257092574. IPSW and helpers in work/local-inferno-vm. Public guide clone ticket differs; downloaded exact app-profile ticket from chefkiss.dev, SHA4380ca...419db90 verified, never substitute clone template. prepare.py/run.py new experimental local tools; preparation/restore not yet run. Full cloud run39265025275 checked completed/cancelled; no new cloud restore dispatched. Next: start image preparation, patch stock RAM disk, run exactly one local restore container. No SpringBoard/UI proof yet.

Local restore is now running in detached Docker container inferno-local-restore (image inferno-local:bql-test), bound to localhost5900/4444/5555,6CPUs/6GiB, files work/local-inferno-vm. Earlier stopped containers retained with suffix missing-keymaps and bql-failure; never start those. Reused34VNC keymaps from the exact IPA after first boot revealed missing en-us. Real local guest startup exposed backendb533 BQL assertion at first USB RESET. Candidate corecommit fbbbf4ed18a43fb5f32a0de23a5ccca8c9f5f4cc adds scoped device-state protection after socket coroutine reads (no newly acquired BQL held across socket writes). Native Linux incremental build passed; actual guest USB enumerated, restored and ASR connected, NORData sent, real ASR restore observed4%. Candidate running image differs from commit only by whitespace cleanup. No normal boot/SpringBoard/patcher-done yet. Logs private under work/local-inferno-vm/restore-logs. Current supervisor waits for ListDevices before launching idevicerestore. Do not restart or duplicate the running VM; inspect actual current logs/QMP. Automation was found PAUSED; do not resume stale cloud prompt blindly.


At19:14Moscow local real ASR restore reached82% and QMP query-status reports running; guest patcher active, waiting at volume-mask23. No panic/finalStatus/patcher-done yet. A host observer is ACTIVE (exec session63259), command tools/local-restore/watch.py work/local-inferno-vm --handoff, file work/local-inferno-vm/watch.log and atomic-ish JSON local-restore-observation.json. It performs the same QMP system-boot-after-restore reset as the app ONLY after stock idevicerestore Status: Restore Finished AND explicit patcher-done. It never claims SpringBoard or stops a VM on timeout/failure. Check current process/container before starting another observer or restore. This observer addition is local app commit511d5f9, not yet pushed; corecandidatefbbbf4e and initial local-tools817eb86 already pushed. App code-check run39283123683 queued, no extra restores. VNC frame captured locally was only Apple logo/progress bar, not UI proof.


## CURRENT — local retry after QMP assertion,19October2026
The first local restore reached100% ASR write and100% verify, then merging APFS fsroot tree. My read-only query-blockstats diagnostic triggered a separate backend fatal assertion bdrv_graph_rdlock_main_loop/qemu_in_main_thread; QEMU exited and restore did NOT finish. Retained work/local-inferno-vm and stopped container inferno-local-restore-qmp-failure. Stopped its observerPID2764. Reproduced the QMP assertion on a separate PAUSED t8030 machine: readonly firmware mount, no guest execution/disks, only tiny temporary probe disks. Added scoped BQL guard to qapi/qmp-dispatch.c do_qmp_dispatch_bh; corecommit87af92296132800974511dc1d049929d4bafc9e2 (not yet pushed), native image inferno-local:qmp-test. Ten query-blockstats calls passed and machine remained prelaunch. Probe containers stopped; never start them as guest VMs.
CURRENT active restoration container inferno-local-restore now uses inferno-local:qmp-test and VM folder work/local-inferno-vm-qmp-sparse. All mutable disks freshly blank; immutable IPSW/boot inputs hardlinked to original. Windows sparse disks created using native SetEndOfFile (Python CRT truncate zero-fills). The abandoned work/local-inferno-vm-qmp-fixed is only a partial blank-disk creation, never a guest; do not boot it. Disk space ~37GB remains, preserve failed VM but avoid large additional full raw copies. A first attempt with the new folder failed before guest startup due omitted VNC keymaps. Added keymap copy/preflight and restarted the same untouched blank set; do not describe that preflight as restore progress. Latest container restarted after user said continue; inspect current logs. Existing watcherPID19060 / exec83960 remains the ONLY observer: tools/local-restore/watch.py work/local-inferno-vm-qmp-sparse --handoff, writes that folder/watch.log and observationJSON. Do not duplicate. It gates QMP handoff on both final Status: Restore Finished and patcher-done. No SpringBoard/cold-boot proof. User additionally wants to try the desktop GUI after successful boot; provide interactive window when ready. Production default still37d6816, experimental IPA remains old10ef170/backendb533, not this candidate.


Current retry passed USB enumeration/NOR and ASR writing64% with image inferno-local:qmp-test, both core fixes87af922 (now pushed). Running actual VM folder remains work/local-inferno-vm-qmp-sparse. Viewer is prepared in inferno-local-viewer; Ubuntu packaged noVNC/websockify, HTTP200 at127.0.0.1:6080, actual backend RFB003.008 reachable through Docker network inferno-local-ui. Viewer also attached to bridge because internal-only Docker networks did not publish localhost port. NOT opened to user yet; they want to try it only after real UI. No guest UI/SpringBoard claim from viewer. Removed only agent-created aborted zero-filled scratch disk local-inferno-vm-qmp-fixed/InfernoData/root (31.6GB, helper stopped, no restore logs/no guest ever used it), after checking path and active container mounts. Actual failed VM and current guest preserved; ~64GB free restored. Do not create another full raw copy until current VM stopped; cold test still required after success. Observer PID19060/execution83960 continues. Do not start another.


## CURRENT — successful local restore, patcher recovery pending,19October19:55Moscow
Actual idevicerestore ended Status: Restore Finished / DONE /100% on backend87af922 (inferno-local:qmp-test). This is restore success, NOT guest UI proof. Patcher mounted System and started analysing1957MB dyld cache, but restored_external immediately initiated reboot; XNU panicked Halt/Restart Timed Out before patcher-done. hold-reset blocks machine reset but not the guest shutdown deadline. Container inferno-local-restore is now confirmed EXITED. Original successful restore logs retained in work/local-inferno-vm-qmp-sparse/restore-logs.
A stopped-disk backup is currently copying all9 mutable disks to that VM folder/pre-patch-backup via Docker cp --sparse=always. Copy exec63207/container trusting_mcnulty; do not boot current disks until copy and sync finish. Root backup was explicitly marked NTFS sparse while copy active. No erase restore is running. Viewer remains localhost6080.
Local tools now add mutually exclusive --patch-only: boot existing installed disks with patched RAMdisk but NEVER launch idevicerestore; requires exact successful restore log. New patch-only-logs preserve prior failure evidence. watch.py --patch-only --handoff reads those new logs and prior successful client log, blocks handoff on any panic/failure. Python compile/help checks passed; this recovery mode has NOT yet booted. Official pinned FSPatcher3008aaaa builds changes before flush and supports original-byte revert, but actual guest completion still unconfirmed. Next: verify backup completed, rename stopped restore container, launch ONE --patch-only container using same VM, observe actual patcher. Stock restored_external may time out waiting for host; inspect evidence before changing boot content. No SpringBoard/backboardd/cold boot/iPhone proof. App codechecks39283123683 succeeded but did not execute guest iOS. No production pin promotion or new IPA.

## CURRENT — patch-only boot actually mounted installed System,20:01Moscow
Stopped-disk backup of ALL9 mutable disks completed with matching full SHA-256 hashes in private pre-patch-backup/verified.json (root32GiB hash7468b6...3758). Docker sparse copy was too slow; stopped it and completed native Windows allocated-range copy with full verification. Backup retained, not hardlinks. New backup_windows.py checks writable running Docker mounts before future use.
First patch-only recovery-mode boot exposed AppleEmbeddedNVMeController FW-update-not-complete dummy disk; no installed partitions were visible. Stopped VM and observer; logs retained in patch-only-recovery-mode-logs, container inferno-patch-only-dummy-storage EXITED. That attempt did not run idevicerestore.
Second patch-only experiment removes automatic -restore/nand-enable-reformat by using exit_recovery plus explicit rd=md0 while still attaching RAMdisk. Separate patch-only-ramdisk.im4p built with original signed helpers and app HFS editor; only additional plist edit disables com.apple.restored_external, preventing its host-wait/reboot timer. Original restore RAMdisk preserved. Native Swift6.2 CLI built and produced exact104685595byte image. Actual guest now sees both installed volumes, mount_apfs System returned0, patcher analysing1957MB shared cache. No patcher-done/UI proof yet.
ONLY current VM container inferno-local-restore ID02b4f1e06da04edf7a8494aed71377fb49cc103f7e47dad966e465e12e179971, same inferno-local:qmp-test/core87af922, same folder local-inferno-vm-qmp-sparse, --patch-only, localhost5900/4444/5555. ONE observer execution67499, watch.py --patch-only --handoff. Check actual current logs before doing anything. Backup complete means no more copy waiting. Old observer19492 stopped. Current logs patch-only-logs. Continue awaiting bounded patcher result; on success observer performs explicit normal-boot handoff, does not claim UI. Need actual process evidence/frame/cold boot afterward. Commit4bca92d pushed; later recovery changes currently working tree. Production/IPA unchanged.
