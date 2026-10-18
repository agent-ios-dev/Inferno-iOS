# Automatic setup fork

This unofficial fork belongs to agent-ios-dev. Original app: MakrSas/Inferno-iOS;
original emulator: ChefKissInc/Inferno, with MakrSas's iOS port. Existing authors,
licences and attribution are retained. No Apple firmware or device image is
bundled in the app or committed here.

## New first-launch path

Choose **Автоматически → Создать виртуальный iPhone**. The app checks JIT,
downloads the fixed iPhone 11 iOS 14 beta 5 profile, prepares the existing
RestorePrep kit, starts the real in-app USB restore and waits for successful
filesystem patching. There is no manual file picker in this path. The guest's
real display and touchscreen/buttons are provided by the existing Inferno port.

StikDebug must already have its pairing/VPN setup. The button requests
`stikdebug://enable-jit` for this app's bundle/PID with `legacy.js`. Returning to
the app repeats the real JIT availability check before proceeding. The app cannot
create the host phone's debugger permissions itself.

The fork uses `dev.agent-ios.inferno` (macOS: `dev.agent-ios.inferno.mac`),
separate from the upstream app, to avoid replacing its existing guest/data.
The StikDebug request uses the installed bundle identifier, including one
changed by a sideloading tool.

Allow 20 GiB of free host storage initially, and keep the app in the foreground.
The IPSW is downloaded directly into the private restore directory, so a second
multi-gigabyte copy is unnecessary. Completed downloads are reused; cancellation
discards only the current URLSession temporary download. Partially downloaded
IPSW data is currently downloaded again. Named assets are never adopted from
outside this operation. Existing guest disks/prepared firmware are refused.

## Fixed inputs and checks

- IPSW: Apple's `updates.cdn-apple.com`, build 18A5351d, 5,507,405,643 bytes;
  the app checks ZIP identity, ProductVersion/ProductBuildVersion and n104ap's
  erase-install identity. This does not claim a full IPSW SHA-256 verification.
- Ticket: `https://chefkiss.dev/Extras/Inferno/ticket.shsh2`, 79,421 bytes;
  SHA-256 pinned in AutomaticSetupProfile.swift.
- SEP ROM: `https://securerom.fun/resources/SEPROM/AppleSEPROM-Cebu-B1`,
  86,016 bytes; SHA-256 pinned in AutomaticSetupProfile.swift.
- Public build-specific SEP firmware IV/key: The Apple Wiki,
  `Keys:AzulSeed 18A5351d (iPhone12,1)`, SEP-Firmware section. These are published
  firmware parameters, not host-device credentials. They are never logged.

Only the three fixed HTTPS hosts are accepted for download redirects. Failed
size/hash checks stop preparation. A missing required patcher stops before erase.
Filesystem patcher failure, a missing shared cache and a patcher timeout all fail
the installation instead of reporting it completed. Only an explicit success
marker from the current boot allows the next stage.

## Restore to normal boot

QEMU cannot be initialized twice in the app process. This fork uses its own
backend (`agent-ios-dev/Inferno`, commit
37d68169800a2e41de7da7e96478a15ac4431ca7) to switch the **same paused VM** from
the restore RAM disk to normal disk boot over QMP, followed by system_reset/cont.
The machine's SEP, NVMe data and ticket remain the ones created by the restore;
no keybag state is fabricated. A protocol error leaves the disk intact and is
reported. After an interrupted VM session, relaunch the app before retrying.

## Verification and present limits

`Verify automatic setup` tests the actual Swift input validators and typechecks
all shared app sources for iOS and macOS. `Build Inferno.ipa` builds the pinned
backend, display dependency and required guest patcher. `Restore real iOS from
an empty folder` runs the actual Swift controller on a macOS runner with no
prepared firmware/image input, then records a screenshot from its framebuffer.
Only metadata and the screenshot are uploaded; no guest disk, firmware or keys.

Compilation and input tests are not proof of a working phone installation.
The full restore/reset path and physical StikDebug execution still require
runtime confirmation. A captured frame is not automatically called SpringBoard;
it must be inspected. The downloaded profile does not add a jailbreak bootstrap,
so features requiring the guest's bash/bootstrap are not promised by this path.
