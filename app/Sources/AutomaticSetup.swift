import Foundation
import Combine
#if os(iOS)
import UIKit
#endif

/// Owns the whole first-install operation, rather than exposing its files to
/// the person using the app. Never adopts or erases a manually installed VM.
@MainActor final class AutomaticSetup: ObservableObject {
    static let shared = AutomaticSetup()
    @Published private(set) var busy = false
    @Published private(set) var waitingForJIT = false
    @Published private(set) var message = "iPhone 11 · iOS 14 beta 5. Файлы скачиваются и настраиваются автоматически."
    @Published private(set) var fraction = 0.0
    @Published private(set) var pending = UserDefaults.standard.bool(forKey: "automaticSetupPending")
    private var download: AutomaticSetupDownload?
    private var operation: Task<Void, Never>?
    private var subscriptions = Set<AnyCancellable>()
    private var restoreFinished = false
    private weak var model: VMModel?
    private let defaults = UserDefaults.standard
    private var cache: URL { VMConfig.documents.appendingPathComponent("SetupDownloads") }
    private var checkpoint: URL { VMConfig.documents.appendingPathComponent("AutomaticSetup.plist") }

    func start(model: VMModel) {
        guard !busy, !model.isRunning else { return }
        self.model = model
        model.refreshJIT()
        guard model.config.virtualization || model.jit.isAvailable else {
            waitingForJIT = true
            message = "Включи JIT через StikDebug, назначив приложению legacy.js, и вернись сюда. Подготовка продолжится автоматически."
            return
        }
        waitingForJIT = false; busy = true
        #if os(iOS)
        UIApplication.shared.isIdleTimerDisabled = true
        #endif
        operation = Task {
            do {
                try claimEmptyMachine()
                guard let free = RestoreSession.freeSpace, free > 20 * 1_073_741_824 else {
                    throw AutomaticSetupProfile.Failure.invalid("Для первой установки нужно минимум 20 ГБ свободного места")
                }
                guard RestoreRamdisk.programs != nil else {
                    throw AutomaticSetupProfile.Failure.invalid("В сборке нет обязательного патчера. Восстановление не запущено.")
                }
                var paths: [URL] = []
                for asset in AutomaticSetupProfile.assets {
                    try Task.checkCancellation()
                    message = "Загрузка: \(asset.name)"; fraction = 0
                    let parent = asset.name == AutomaticSetupProfile.firmware.name ? VMConfig.dataDirectory : cache
                    try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
                    let file = parent.appendingPathComponent(asset.name)
                    if (try? AutomaticSetupProfile.validateFile(file, asset: asset)) == nil {
                        // Only remove this operation's named download, never a VM.
                        if FileManager.default.fileExists(atPath: file.path) { try FileManager.default.removeItem(at: file) }
                        let transfer = AutomaticSetupDownload(asset: asset, destination: file) { [weak self] value in
                            Task { @MainActor in self?.fraction = value }
                        }
                        download = transfer
                        _ = try await transfer.run(); download = nil
                    }
                    paths.append(file)
                }
                let prepared = defaults.string(forKey: "automaticSetupPrepared") == AutomaticSetupProfile.id
                if !prepared {
                    message = "Проверка прошивки и подготовка дисков…"
                    let firmware = paths[0], ticket = paths[1], rom = paths[2]
                    try await Task.detached(priority: .userInitiated) { [weak self] in
                        let ipsw = try IPSW(url: firmware)
                        try AutomaticSetupProfile.validateManifest(Data(ipsw.read("BuildManifest.plist")))
                        try RestorePrep.prepare(.init(ipsw: firmware, shsh2: ticket, sepROM: rom,
                            sepKey: AutomaticSetupProfile.sepKey, cryptexTemplate: nil), note: { note in
                                LogCapture.shared.note(note)
                                Task { @MainActor in self?.message = note }
                            }, progress: { value in Task { @MainActor in self?.fraction = value } })
                    }.value
                    defaults.set(AutomaticSetupProfile.id, forKey: "automaticSetupPrepared")
                }
                try Task.checkCancellation()
                // Use the working display; settings from a console-only session
                // must not silently turn a first install into a black screen.
                Settings.shared.headless = false
                Settings.shared.builtInDisplay = true
                #if os(iOS)
                Settings.shared.memory = "2G"
                #endif
                model.refreshFiles()
                guard model.missing.isEmpty else {
                    throw AutomaticSetupProfile.Failure.invalid("Подготовка не завершена: \(model.missing.joined(separator: ", "))")
                }
                observeRestore(model: model)
                message = "Запуск восстановления iOS…"
                RestoreSession.shared.start(model: model, keepRunningForSystemBoot: true)
                Task { [weak self] in
                    try? await Task.sleep(nanoseconds: 60_000_000_000)
                    guard let self, self.busy, !self.restoreFinished, !model.isRunning else { return }
                    RestoreSession.shared.stop()
                    self.fail("Эмулятор не запустился. Проверь JIT через StikDebug; скачанные файлы сохранены.")
                }
            } catch { fail(error.localizedDescription) }
        }
    }

    private func claimEmptyMachine() throws {
        let manager = FileManager.default
        if manager.fileExists(atPath: checkpoint.path) {
            let data = try Data(contentsOf: checkpoint)
            guard let saved = try PropertyListSerialization.propertyList(from: data, format: nil) as? [String: String],
                  saved["profile"] == AutomaticSetupProfile.id else {
                throw AutomaticSetupProfile.Failure.invalid("Набор относится к другой версии. Существующая машина сохранена.")
            }
        } else {
            let existing = (try? manager.contentsOfDirectory(atPath: VMConfig.dataDirectory.path)) ?? []
            let reserved = Set(RestorePrep.disks.map(\.name) + ["root.qcow2", "root_ticket.der", "Restore"])
            guard existing.allSatisfy({ !reserved.contains($0) }) else {
                throw AutomaticSetupProfile.Failure.invalid("Уже найдена другая машина. Автонастройка не будет её перезаписывать.")
            }
            try manager.createDirectory(at: VMConfig.documents, withIntermediateDirectories: true)
            let data = try PropertyListSerialization.data(fromPropertyList: ["profile": AutomaticSetupProfile.id], format: .xml, options: 0)
            try data.write(to: checkpoint, options: .atomic)
        }
        try manager.createDirectory(at: cache, withIntermediateDirectories: true)
        pending = true; defaults.set(true, forKey: "automaticSetupPending")
    }

    private func observeRestore(model: VMModel) {
        subscriptions.removeAll(); restoreFinished = false
        RestoreSession.shared.$stage.receive(on: DispatchQueue.main).sink { [weak self] stage in
            guard let self, self.busy else { return }
            switch stage {
            case .restoring(let text, let value): self.message = text; self.fraction = value
            case .waitingForDevice: self.message = "Ожидание установщика гостевой iOS…"
            case .failed(let why): self.fail(why)
            case .done:
                self.restoreFinished = true
                self.message = "Система восстановлена. Переход к обычной загрузке…"
                self.bootRestoredMachine(model)
            default: break
            }
        }.store(in: &subscriptions)
        model.$qemuState.receive(on: DispatchQueue.main).sink { [weak self] state in
            guard let self, self.busy else { return }
            if case .failed(let why) = state { self.fail(why) }
            if case .stopped = state { self.fail("Эмулятор остановился во время восстановления. Скачанные файлы и диск сохранены.") }
        }.store(in: &subscriptions)
    }

    private func bootRestoredMachine(_ model: VMModel) {
        guard restoreFinished, model.isRunning else { return }
        restoreFinished = false
        let port = model.config.qmpPort
        Task {
            do {
                try await Task.detached { try RestoreBootHandoff.run(port: port) }.value
                subscriptions.removeAll()
                RestoreSession.shared.stop()
                pending = false; defaults.set(false, forKey: "automaticSetupPending")
                model.refreshFiles()
                busy = false; message = "Загрузка iOS. Ожидаем изображение гостевой системы."
                #if os(iOS)
                UIApplication.shared.isIdleTimerDisabled = false
                #endif
            } catch { fail(error.localizedDescription) }
        }
        // A completed reset is not proof of visible SpringBoard.
    }

    func returned(model: VMModel) { if waitingForJIT { start(model: model) } }
    func cancelDownload() {
        guard download != nil else { return }
        operation?.cancel(); download?.cancel()
    }
    private func fail(_ why: String) {
        busy = false; waitingForJIT = false
        message = "Автонастройка остановлена: \(why)"
        LogCapture.shared.note(message)
        subscriptions.removeAll()
        #if os(iOS)
        UIApplication.shared.isIdleTimerDisabled = false
        #endif
    }
}
