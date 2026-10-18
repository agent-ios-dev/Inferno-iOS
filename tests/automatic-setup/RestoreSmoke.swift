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
        let output = URL(fileURLWithPath: ProcessInfo.processInfo.environment["INFERNO_SMOKE_OUTPUT"]!)
        try! FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        func report(_ reason: String) {
            // Export only fixed booleans, never raw firmware/SEP console lines.
            let hostLog = LogCapture.shared.text
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
                "asr_socket_opened": hostLog.contains("Restore: ASR on port"),
                "asr_validation_completed": hostLog.contains("Restore: the image is validated, sending it"),
                "asr_payload_sent": hostLog.contains("Restore: the whole system image is sent"),
                "guest_usbmux_sequence_error": guestLog.contains("detected duplicate packet"),
                "guest_kernel_panic": guestLog.contains("panic(cpu"),
                "guest_panic_summary": panicSummary,
                "guest_checksum_failure": guestLog.lowercased().components(separatedBy: .newlines).contains {
                    $0.contains("checksum") && ($0.contains("fail") || $0.contains("mismatch"))
                },
                "machine_running": model.isRunning, "guest_frame_received": model.picture.image != nil,
                "visible_springboard_confirmed": false, "physical_iphone_confirmed": false]
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
                    report("automatic setup failed")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(1) }
                }
                if !setup.pending && !setup.busy && model.isRunning && restoredAt == nil { restoredAt = Date() }
                if let restoredAt, Date().timeIntervalSince(restoredAt) > 900 {
                    finished = true
                    report("post-restore observation completed; screenshot requires visual inspection")
                    let success = model.picture.image != nil
                    DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(success ? 0 : 1) }
                }
                if Date().timeIntervalSince(started) > 6300 {
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
