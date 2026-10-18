import Foundation
import Darwin

// Only the surrounding UI/configuration is stubbed. GuestUSB is compiled from
// the app unchanged; the peer implements the emulator's packed USB protocol.
enum VMConfig { static let usbSocketName = "test"; static let socketDirectory = "/tmp" }
final class LogCapture { static let shared = LogCapture(); func note(_ value: String) {} }
func L(_ format: String, _ args: CVarArg...) -> String { String(format: format, arguments: args) }

func readExactly(_ fd: Int32, _ count: Int) -> [UInt8]? {
    var bytes = [UInt8](repeating: 0, count: count), at = 0
    while at < count {
        let n = bytes.withUnsafeMutableBytes { Darwin.read(fd, $0.baseAddress!.advanced(by: at), count - at) }
        if n <= 0 { return nil }; at += n
    }
    return bytes
}
func writeAll(_ fd: Int32, _ bytes: [UInt8]) {
    var at = 0
    while at < bytes.count {
        let n = bytes.withUnsafeBytes { Darwin.write(fd, $0.baseAddress!.advanced(by: at), bytes.count - at) }
        precondition(n > 0); at += n
    }
}

func verify(_ size: Int, truncate: Bool = false) throws {
    var pair: [Int32] = [0, 0]
    precondition(socketpair(AF_UNIX, SOCK_STREAM, 0, &pair) == 0)
    let peer = pair[1], host = pair[0]
    var timeout = timeval(tv_sec: 10, tv_usec: 0)
    for fd in pair { setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue: timeout))) }
    let expected = (0..<size).map { UInt8(truncatingIfNeeded: $0) }
    let done = DispatchSemaphore(value: 0)
    DispatchQueue.global().async {
        defer { Darwin.close(peer); done.signal() }
        var received: [UInt8] = [], refusedOnce = false
        while let request = readExactly(peer, 23) {
            precondition(request[0] == 1)
            let wanted = Int(request[21]) | Int(request[22]) << 8
            let incoming = request[2] == 0x69
            let payload = incoming ? [] : (readExactly(peer, wanted) ?? [])
            // Model a descriptor accepting a short prefix of an oversized OUT.
            // This exposed the old transport's silent loss of the suffix.
            let accepted = incoming ? 0 : min(wanted, truncate ? 1 : 512)
            let nak = incoming || !refusedOnce
            if !incoming && !refusedOnce { refusedOnce = true }
            var reply: [UInt8] = [2, request[1]]
            reply += Array(request[2..<6]) + [request[6]] + Array(request[7..<15])
            reply += nak ? [254, 255, 255, 255] : [0, 0, 0, 0]
            reply += nak ? [0, 0] : [UInt8(accepted & 255), UInt8(accepted >> 8)]
            writeAll(peer, reply)
            if !nak { received += payload.prefix(accepted) }
            if truncate && !nak { return }
            if received.count == expected.count {
                precondition(received == expected, "USB OUT bytes were lost or duplicated")
                return
            }
        }
        preconditionFailure("transport closed before all bytes were received")
    }
    let usb = GuestUSB(testSocket: host)
    defer { Darwin.close(host) }
    do {
        try usb.testBulkOut(expected)
        precondition(!truncate, "short OUT success was silently accepted")
    } catch {
        guard truncate, error.localizedDescription.contains("incomplete OUT") else { throw error }
    }
    precondition(done.wait(timeout: .now() + 15) == .success)
}

try verify(16383)
try verify(16384)
try verify(511)
try verify(512)
try verify(512, truncate: true)
print("Real GuestUSB: full frame preserved across descriptor boundaries, NAK retries and short-OUT rejection passed")
