import Foundation

/// Executes on QMP's main-loop/BQL path. Reinitializing QEMU would terminate
/// this app; reset the same machine after changing only its restore boot source.
enum RestoreBootHandoff {
    static func run(port: UInt16) throws {
        let socket = Sock()
        defer { socket.close() }
        if let reason = socket.connect(port: port) { throw AutomaticSetupProfile.Failure.invalid(reason) }
        var pending = Data()
        func object() throws -> [String: Any] {
            let deadline = Date().addingTimeInterval(30)
            while Date() < deadline {
                if let newline = pending.firstIndex(of: 10) {
                    let line = pending.prefix(upTo: newline)
                    pending.removeSubrange(...newline)
                    guard let parsed = try JSONSerialization.jsonObject(with: line) as? [String: Any] else {
                        throw AutomaticSetupProfile.Failure.invalid("Некорректный ответ QMP")
                    }
                    return parsed
                }
                guard pending.count < 262144, let chunk = socket.readSome(max: 65536), !chunk.isEmpty else {
                    throw AutomaticSetupProfile.Failure.invalid("QMP закрыл соединение при переходе к системе")
                }
                pending.append(contentsOf: chunk)
            }
            throw AutomaticSetupProfile.Failure.invalid("Истекло время ответа QMP")
        }
        guard try object()["QMP"] != nil else { throw AutomaticSetupProfile.Failure.invalid("Нет приветствия QMP") }
        let commands: [(String, [String: Any]?)] = [
            ("qmp_capabilities", nil), ("stop", nil),
            ("qom-set", ["path": "/machine", "property": "system-boot-after-restore", "value": true]),
            ("system_reset", nil), ("cont", nil)
        ]
        for (index, entry) in commands.enumerated() {
            var request: [String: Any] = ["execute": entry.0, "id": index]
            if let arguments = entry.1 { request["arguments"] = arguments }
            let data = try JSONSerialization.data(withJSONObject: request)
            guard socket.write([UInt8](data) + [10]) else { throw AutomaticSetupProfile.Failure.invalid("Не удалось отправить \(entry.0)") }
            while true {
                let reply = try object()
                guard (reply["id"] as? NSNumber)?.intValue == index else { continue }
                if let error = reply["error"] as? [String: Any] {
                    throw AutomaticSetupProfile.Failure.invalid("Переход к системе: \(error["desc"] as? String ?? entry.0)")
                }
                guard reply["return"] != nil else { throw AutomaticSetupProfile.Failure.invalid("QMP не подтвердил \(entry.0)") }
                break
            }
        }
    }
}
