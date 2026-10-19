import Foundation

/// Read-only process existence evidence from the live guest, never console guesses.
enum BootProcessEvidence {
    static let command = "if command -v pgrep >/dev/null 2>&1; then a=$(pgrep -x SpringBoard 2>/dev/null); r=$?; b=$(pgrep -x backboardd 2>/dev/null); s=$?; if [ \"$r\" -le 1 ] && [ \"$s\" -le 1 ]; then printf INFERNO_PS_OK; for p in $a; do printf '|SpringBoard=%s' \"$p\"; done; for p in $b; do printf '|backboardd=%s' \"$p\"; done; else printf INFERNO_PS_ERROR; fi; else printf INFERNO_PS_UNAVAILABLE; fi"

    static func parse(_ response: String) -> [[String: Any]]? {
        guard response.utf8.count <= 2048 else { return nil }
        let fields = response.trimmingCharacters(in: .whitespacesAndNewlines).split(separator: "|", omittingEmptySubsequences: false)
        guard fields.first == "INFERNO_PS_OK", fields.count <= 17 else { return nil }
        var seen = Set<Int>()
        var result: [[String: Any]] = []
        for field in fields.dropFirst() {
            let pair = field.split(separator: "=", omittingEmptySubsequences: false)
            guard pair.count == 2, ["SpringBoard", "backboardd"].contains(String(pair[0])),
                  pair[1].allSatisfy({ $0.isASCII && $0.isNumber }),
                  let pid = Int(pair[1]), pid > 0, pid <= Int(Int32.max), seen.insert(pid).inserted
            else { return nil }
            result.append(["name": String(pair[0]), "pid": pid])
        }
        return result
    }
}
