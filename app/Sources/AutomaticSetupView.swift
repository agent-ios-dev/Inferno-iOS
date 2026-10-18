import SwiftUI
#if os(iOS)
import UIKit
#endif

struct AutomaticSetupSection: View {
    @ObservedObject var model: VMModel
    @ObservedObject private var setup = AutomaticSetup.shared
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.openURL) private var openURL

    var body: some View {
        Section {
            Label("iPhone 11 · iOS 14", systemImage: "iphone")
                .font(.headline)
            Text(setup.message).font(.callout)
            if setup.busy {
                ProgressView(value: setup.fraction)
                Button("Отменить загрузку") { setup.cancelDownload() }
            } else {
                Button(setup.pending ? "Продолжить настройку" : "Создать виртуальный iPhone") {
                    setup.start(model: model)
                }
                .disabled(model.isRunning)
            }
            if setup.waitingForJIT {
                #if os(iOS)
                Button("Включить JIT через StikDebug") {
                    var url = URLComponents()
                    url.scheme = "stikdebug"; url.host = "enable-jit"
                    url.queryItems = [URLQueryItem(name: "bundle-id", value: Bundle.main.bundleIdentifier),
                                      URLQueryItem(name: "pid", value: String(ProcessInfo.processInfo.processIdentifier)),
                                      URLQueryItem(name: "script-name", value: "legacy.js")]
                    if let target = url.url { openURL(target) }
                }
                #endif
                Text("StikDebug нужно один раз настроить с pairing-файлом и VPN. Приложение проверяет реальную возможность JIT перед запуском.")
                    .font(.footnote).foregroundStyle(.secondary)
            }
            if model.isRunning {
                Button("Остановить с сохранением диска") { model.shutdown() }
            }
        } header: {
            Text("Автоматическая установка")
        } footer: {
            Text("Прошивка загружается с Apple, дополнительные компоненты — из источников, указанных в документации Inferno. Нужно 20 ГБ свободного места. Первая установка долгая: оставь приложение открытым. Существующая машина не перезаписывается.")
        }
        .onChange(of: scenePhase) { phase in if phase == .active { setup.returned(model: model) } }
    }
}
