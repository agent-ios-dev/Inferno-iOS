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
        let output = URL(fileURLWithPath: ProcessInfo.processInfo.environment["INFERNO_SMOKE_OUTPUT"]!)
        try! FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
        func report(_ reason: String) {
            var report: [String: Any] = ["profile": AutomaticSetupProfile.id, "reason": reason,
                "seconds": Int(Date().timeIntervalSince(started)), "setup_pending": setup.pending,
                "setup_message": setup.message,
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
                if setup.message != lastMessage {
                    // No console, firmware bytes, SEP key values or raw memory
                    // leave this runner. Progress is app-owned text only.
                    lastMessage = setup.message
                    try? publicProgress.write(contentsOf: Data("Automatic restore: \(lastMessage)\n".utf8))
                }
                if setup.message.hasPrefix("Автонастройка остановлена:") {
                    report("automatic setup failed")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(1) }
                }
                if !setup.pending && !setup.busy && model.isRunning && restoredAt == nil { restoredAt = Date() }
                if let restoredAt, Date().timeIntervalSince(restoredAt) > 900 {
                    report("post-restore observation completed; screenshot requires visual inspection")
                    let success = model.picture.image != nil
                    DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(success ? 0 : 1) }
                }
                if Date().timeIntervalSince(started) > 6300 {
                    report("execution budget exhausted")
                    DispatchQueue.main.asyncAfter(deadline: .now() + 10) { exit(1) }
                }
            }
        }
        setup.start(model: model)
        RunLoop.main.run()
    }
}
