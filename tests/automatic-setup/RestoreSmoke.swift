import Foundation
import ImageIO
import CoreGraphics

@main struct RestoreSmoke {
    @MainActor static func main() {
        Bootstrap.prepareDocuments()
        let publicProgress = FileHandle(fileDescriptor: dup(STDOUT_FILENO), closeOnDealloc: true)
        LogCapture.shared.start()
        Settings.shared.virtualization = false
        Settings.shared.memory = "3G"
        Settings.shared.network = false
        let model = VMModel()
        let setup = AutomaticSetup.shared
        let started = Date()
        var restoredAt: Date?
        var lastMessage = ""
        var lastProgressBucket = -1
        var finished = false
        var consoleOffset: UInt64 = 0
        var consolePartial = ""
        var patcherPhases = Set<String>()
        var volumeMasks = Set<Int>()
        var observedHostStages = Set<String>()
        let hostStages = ["Restore: ASR on port", "Restore: the image is validated, sending it",
            "Restore: the whole system image is sent", "RESTORE-ASR: payload and FIN acknowledged",
            "RESTORE-ASR: peer closed after full payload", "USB-TCP: guest reset channel port=62078",
            "USB-TCP: guest finished channel port=62078"]
        let phaseMarkers: [(String, String)] = [
            ("waiting", "PATCHER: waiting for the restore to finish"),
            ("data-ready", "PATCHER: the data volume is here"),
            ("mounted", "PATCHER: mount_apfs /dev/disk0s1s1 says 0"),
            ("cache-started", "PATCHER: patching "),
            ("child-exited", "PATCHER: the patcher exited with"),
            ("failed", "PATCHER: failed"),
            ("done", "PATCHER: done, the machine can be reset now"),
            ("panic", "panic(cpu")]
        func collectConsolePhases() {
            let hostText = LogCapture.shared.text
            for marker in hostStages where hostText.contains(marker) { observedHostStages.insert(marker) }
            guard let file = try? FileHandle(forReadingFrom: VMConfig.guestConsoleLog) else { return }
            defer { try? file.close() }
            let end = (try? file.seekToEnd()) ?? 0
            if consoleOffset > end { consoleOffset = 0; consolePartial = "" }
            try? file.seek(toOffset: consoleOffset)
            // Keep fixed flags when early boot output leaves the final tail.
            let bytes = file.readData(ofLength: 2_097_152)
            consoleOffset += UInt64(bytes.count)
            let text = consolePartial + String(decoding: bytes, as: UTF8.self)
            if let regex = try? NSRegularExpression(pattern: "PATCHER: volume-mask=([0-9]+)") {
                for match in regex.matches(in: text, range: NSRange(text.startIndex..., in: text)) {
                    if let range = Range(match.range(at: 1), in: text), let mask = Int(text[range]), mask < 128,
                       volumeMasks.insert(mask).inserted {
                        try? publicProgress.write(contentsOf: Data("Guest volume mask: \(mask)\n".utf8))
                    }
                }
            }
            for (phase, marker) in phaseMarkers where text.contains(marker) {
                if patcherPhases.insert(phase).inserted {
                    try? publicProgress.write(contentsOf: Data("Guest phase: \(phase)\n".utf8))
                }
            }
            consolePartial = String(text.suffix(128))
        }
        let output = URL(fileURLWithPath: ProcessInfo.processInfo.environment["INFERNO_SMOKE_OUTPUT"]!)
        try! FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        func report(_ reason: String) {
            collectConsolePhases()
            // Export only fixed booleans, never raw firmware/SEP console lines.
            let hostLog = LogCapture.shared.text
            let fudEvents = hostLog.components(separatedBy: .newlines).compactMap { line -> String? in
                guard let range = line.range(of: "RESTORE-FUD: ") else { return nil }
                let value = String(line[range.upperBound...].prefix(120))
                guard value.allSatisfy({ $0.isASCII && ($0.isLetter || $0.isNumber || " ,-=".contains($0)) }) else { return nil }
                return value
            }
            let lastRequest = hostLog.components(separatedBy: .newlines).last {
                $0.contains("Restore: the guest asks for ")
            }.flatMap { $0.components(separatedBy: "Restore: the guest asks for ").last }.map {
                String($0.prefix(while: { $0.isASCII && ($0.isLetter || $0.isNumber || $0 == ",") }).prefix(80))
            } ?? ""
            let guestLog: String = {
                guard let file = try? FileHandle(forReadingFrom: VMConfig.guestConsoleLog) else { return "" }
                defer { try? file.close() }
                let end = (try? file.seekToEnd()) ?? 0
                try? file.seek(toOffset: end > 2_097_152 ? end - 2_097_152 : 0)
                return String(decoding: file.readData(ofLength: 2_097_152), as: UTF8.self)
            }()
            let panicSummary = guestLog.components(separatedBy: .newlines).first { $0.contains("panic(cpu") }.map {
                // Fresh test VM only. Keep the diagnostic sentence, redact
                // long hex/base64 values and cap it; never export a raw log.
                String($0.replacingOccurrences(of: "(?:0x)?[0-9A-Fa-f]{8,}|[A-Za-z0-9+/=_-]{48,}",
                    with: "<redacted>", options: .regularExpression).prefix(400))
            } ?? ""
            var report: [String: Any] = ["profile": AutomaticSetupProfile.id, "reason": reason,
                "seconds": Int(Date().timeIntervalSince(started)), "setup_pending": setup.pending,
                "setup_message": setup.message,
                "setup_fraction": setup.fraction,
                "observed_guest_phases": patcherPhases.sorted(),
                "observed_volume_masks": volumeMasks.sorted(),
                "fud_events": Array(fudEvents.suffix(30)),
                "restored_channel_reset": observedHostStages.contains("USB-TCP: guest reset channel port=62078"),
                "restored_channel_finished": observedHostStages.contains("USB-TCP: guest finished channel port=62078"),
                "last_restore_request": lastRequest,
                "current_dma_in_failed": hostLog.contains("DWC3-DMA: current IN range failed"),
                "current_dma_out_failed": hostLog.contains("DWC3-DMA: current OUT range failed"),
                "dma_address_space_rejected_range": hostLog.contains("DWC3-DMA: address space rejected current range"),
                "dma_scatter_range_exhausted": hostLog.contains("DWC3-DMA: scatter range exhausted"),
                "dma_failed_out_descriptor_unreadable": hostLog.contains("DWC3-DMA: failed OUT descriptor unreadable"),
                "dma_failed_out_descriptor_not_owned": hostLog.contains("DWC3-DMA: failed OUT descriptor no longer owned"),
                "dma_failed_out_descriptor_buffer_changed": hostLog.contains("DWC3-DMA: failed OUT descriptor buffer changed"),
                "dma_failed_out_descriptor_status_changed": hostLog.contains("DWC3-DMA: failed OUT descriptor status changed"),
                "dart_usb_invalid_table": hostLog.contains("DART-USB: invalid translation table"),
                "dart_usb_unreadable_table": hostLog.contains("DART-USB: unreadable page table"),
                "dart_usb_invalid_page": hostLog.contains("DART-USB: invalid page entry"),
                "dart_usb_page_protection": hostLog.contains("DART-USB: page protection rejected access"),
                "dart_usb_invalidation_busy": hostLog.contains("DART-USB: translation requested during invalidation"),
                "dart_usb_invalidation_waited": hostLog.contains("DART-USB: translation waited for invalidation"),
                "usb_ioerror_controller_reset": hostLog.contains("DWC3-IOERROR: controller reset"),
                "usb_ioerror_guest_endxfer": hostLog.contains("DWC3-IOERROR: guest ENDXFER"),
                "usb_ioerror_queued_nak": hostLog.contains("DWC3-IOERROR: queued packet became NAK"),
                "usb_ioerror_inflight_nak": hostLog.contains("DWC3-IOERROR: inflight dispatch became NAK"),
                "asr_socket_opened": observedHostStages.contains("Restore: ASR on port"),
                "asr_validation_completed": observedHostStages.contains("Restore: the image is validated, sending it"),
                "asr_payload_sent": observedHostStages.contains("Restore: the whole system image is sent"),
                "asr_payload_and_fin_acknowledged": observedHostStages.contains("RESTORE-ASR: payload and FIN acknowledged"),
                "asr_peer_closed_after_full_payload": observedHostStages.contains("RESTORE-ASR: peer closed after full payload"),
                "patcher_waiting": guestLog.contains("PATCHER: waiting for the restore to finish"),
                "patcher_data_volume_ready": guestLog.contains("PATCHER: the data volume is here"),
                "patcher_system_mounted": guestLog.contains("PATCHER: mount_apfs /dev/disk0s1s1 says 0"),
                "patcher_cache_started": guestLog.contains("PATCHER: patching "),
                "patcher_child_exited": guestLog.contains("PATCHER: the patcher exited with"),
                "patcher_failed": guestLog.contains("PATCHER: failed") || guestLog.contains("PATCHER: no shared cache"),
                "patcher_done": guestLog.contains("PATCHER: done, the machine can be reset now"),
                "guest_usbmux_sequence_error": guestLog.contains("detected duplicate packet"),
                "guest_kernel_panic": guestLog.contains("panic(cpu"),
                "guest_panic_summary": panicSummary,
                "guest_checksum_failure": guestLog.lowercased().components(separatedBy: .newlines).contains {
                    $0.contains("checksum") && ($0.contains("fail") || $0.contains("mismatch"))
                },
                "machine_running": model.isRunning, "guest_frame_received": model.picture.image != nil,
                "visible_springboard_confirmed": false, "physical_iphone_confirmed": false]
            // Only four decimal counters from an app-owned diagnostic format.
            // Never export its surrounding emulator output or guest addresses.
            let descriptorPattern = "DWC3-DMA: failed OUT descriptor index=([0-9]+) count=([0-9]+) actual=([0-9]+) total=([0-9]+)"
            if let regex = try? NSRegularExpression(pattern: descriptorPattern),
               let match = regex.matches(in: hostLog, range: NSRange(hostLog.startIndex..., in: hostLog)).last {
                var counters: [String: Int] = [:]
                for (index, key) in ["index", "count", "actual", "total"].enumerated() {
                    if let range = Range(match.range(at: index + 1), in: hostLog), let value = Int(hostLog[range]) {
                        counters[key] = value
                    }
                }
                report["failed_out_descriptor"] = counters
            }
            // Fixed controller counters only; never export raw emulator lines.
            let tcpPattern = "USB-OUT-TCP: port=([0-9]+) window=([0-9]+) inflight=([0-9]+) received=([0-9]+) closed=([0-9]+)"
            if let regex = try? NSRegularExpression(pattern: tcpPattern) {
                report["out_nak_tcp_states"] = regex.matches(in: hostLog,
                    range: NSRange(hostLog.startIndex..., in: hostLog)).suffix(8).map { match in
                    var state: [String: Int] = [:]
                    for (index, key) in ["port", "window", "inflight", "received", "closed"].enumerated() {
                        if let range = Range(match.range(at: index + 1), in: hostLog), let value = Int(hostLog[range]) {
                            state[key] = value
                        }
                    }
                    return state
                }
            }
            let nakPattern = "DWC3-OUT-NAK: ep=([0-9]+) enabled=([0-9]+) transfer=([0-9]+) buffers=([0-9]+) free=([0-9]+) control=([0-9]+) events=([0-9]+) pending=([0-9]+) reason=([0-9]+) first=([0-9]+) trbs=([0-9]+) actual=([0-9]+) total=([0-9]+) naks=([0-9]+)"
            if let regex = try? NSRegularExpression(pattern: nakPattern) {
                report["out_nak_controller_states"] = regex.matches(in: hostLog,
                    range: NSRange(hostLog.startIndex..., in: hostLog)).suffix(8).map { match in
                    var state: [String: Int] = [:]
                    for (index, key) in ["endpoint", "enabled", "transfer", "buffers", "can_free", "control", "events", "pending", "reason", "first", "trbs", "actual", "total", "naks"].enumerated() {
                        if let range = Range(match.range(at: index + 1), in: hostLog), let value = Int(hostLog[range]) {
                            state[key] = value
                        }
                    }
                    return state
                }
            }
            if let image = model.picture.image {
                let path = output.appendingPathComponent("guest-screen.png")
                if let writer = CGImageDestinationCreateWithURL(path as CFURL, "public.png" as CFString, 1, nil) {
                    CGImageDestinationAddImage(writer, image, nil)
                    report["screenshot_written"] = CGImageDestinationFinalize(writer)
                }
            }
            try? JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys])
                .write(to: output.appendingPathComponent("restore-smoke.json"))
            model.shutdown()
        }
        Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { _ in
            Task { @MainActor in
                guard !finished else { return }
                collectConsolePhases()
                let bucket = Int(max(0, min(1, setup.fraction)) * 20)
                if setup.message != lastMessage || bucket != lastProgressBucket {
                    // No console, firmware bytes, SEP key values or raw memory
                    // leave this runner. Progress is app-owned text only.
                    lastMessage = setup.message
                    lastProgressBucket = bucket
                    try? publicProgress.write(contentsOf: Data("Automatic restore: \(lastMessage) [\(bucket * 5)%]\n".utf8))
                }
                if setup.message.hasPrefix("Автонастройка остановлена:") {
                    finished = true
                    // A rejected DMA can raise a guest interrupt before its
                    // panic text reaches the serial file. Keep the stopped
                    // restore's VM alive briefly; don't mistake an immediate
                    // snapshot for evidence that the guest never panicked.
                    DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                        report("automatic setup failed; observed guest for five more seconds")
                        DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(1) }
                    }
                }
                if !setup.pending && !setup.busy && model.isRunning && restoredAt == nil { restoredAt = Date() }
                if let restoredAt, Date().timeIntervalSince(restoredAt) > 900 {
                    finished = true
                    report("post-restore observation completed; screenshot requires visual inspection")
                    let success = model.picture.image != nil
                    DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(success ? 0 : 1) }
                }
                if Date().timeIntervalSince(started) > 10800 {
                    finished = true
                    report("execution budget exhausted")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(1) }
                }
            }
        }
        setup.start(model: model)
        RunLoop.main.run()
    }
}
