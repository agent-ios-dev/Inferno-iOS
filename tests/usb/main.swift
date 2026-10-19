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

func verify(_ size: Int, truncate: Bool = false, inError: Bool = false) throws {
    var pair: [Int32] = [0, 0]
    precondition(socketpair(AF_UNIX, SOCK_STREAM, 0, &pair) == 0)
    let peer = pair[1], host = pair[0]
    var timeout = timeval(tv_sec: 10, tv_usec: 0)
    for fd in pair { setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, socklen_t(MemoryLayout.size(ofValue: timeout))) }
    let expected = (0..<size).map { UInt8(truncatingIfNeeded: $0) }
    let done = DispatchSemaphore(value: 0)
    DispatchQueue.global().async {
        defer { Darwin.close(peer); done.signal() }
        var received: [UInt8] = [], outAttempts = 0
        while let request = readExactly(peer, 23) {
            precondition(request[0] == 1)
            let wanted = Int(request[21]) | Int(request[22]) << 8
            let incoming = request[2] == 0x69
            let payload = incoming ? [] : (readExactly(peer, wanted) ?? [])
            // Model a descriptor accepting a short prefix of an oversized OUT.
            // This exposed the old transport's silent loss of the suffix.
            if !incoming { outAttempts += 1 }
            // First NAK, then SUCCESS with zero consumed bytes: both must
            // retry the same payload. A later short positive result must fail.
            let accepted = incoming || outAttempts == 2 ? 0 : min(wanted, truncate ? 1 : 512)
            let nak = incoming || outAttempts == 1
            var reply: [UInt8] = [2, request[1]]
            reply += Array(request[2..<6]) + [request[6]] + Array(request[7..<15])
            reply += incoming && inError ? [251, 255, 255, 255] : (nak ? [254, 255, 255, 255] : [0, 0, 0, 0])
            reply += nak ? [0, 0] : [UInt8(accepted & 255), UInt8(accepted >> 8)]
            writeAll(peer, reply)
            if incoming && inError { return }
            if !nak { received += payload.prefix(accepted) }
            if truncate && !nak && accepted > 0 { return }
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
        precondition(!truncate && !inError, "short OUT success or IN failure was silently accepted")
    } catch {
        if inError {
            guard error.localizedDescription.contains("status -5, token 105") else { throw error }
        } else {
            guard truncate, error.localizedDescription.contains("incomplete OUT") else { throw error }
        }
    }
    precondition(done.wait(timeout: .now() + 15) == .success)
}

try verify(16383)
try verify(16384)
try verify(511)
try verify(512)
try verify(512, truncate: true)
try verify(512, inError: true)

// Reproduce the lock inversion: a data frame's first packet is NAKed until
// the peer sees an ACK. No mux number may be skipped or replayed, and no ACK
// may be inserted in the middle of an already accepted frame.
func verifyAckPriority() throws {
    var pair: [Int32] = [0, 0]
    precondition(socketpair(AF_UNIX, SOCK_STREAM, 0, &pair) == 0)
    let usb = GuestUSB(testSocket: pair[0])
    let done = DispatchSemaphore(value: 0)
    let payload = [UInt8](repeating: 0xA5, count: 100)
    DispatchQueue.global().async {
        defer { Darwin.close(pair[1]); done.signal() }
        var stage = 0
        while let request = readExactly(pair[1], 23) {
            let wanted = Int(request[21]) | Int(request[22]) << 8
            let incoming = request[2] == 0x69
            let bytes = incoming ? [] : (readExactly(pair[1], wanted) ?? [])
            var nak = incoming
            if !incoming {
                if stage == 0 {
                    precondition(bytes.count == 116 && bytes[12] == 0 && bytes[13] == 0)
                    usb.testQueueAck() // Queue while writer owns the send lock.
                    nak = true; stage = 1
                } else if stage == 1 {
                    precondition(bytes.count == 36 && bytes[12] == 0 && bytes[13] == 0,
                                 "ACK must use the unconsumed frame's mux number")
                    precondition(bytes[29] == 0x10)
                    stage = 2
                } else {
                    precondition(bytes.count == 116 && bytes[12] == 0 && bytes[13] == 1)
                    precondition(Array(bytes.dropFirst(16)) == payload)
                    stage = 3
                }
            }
            var reply: [UInt8] = [2, request[1]]
            reply += Array(request[2..<6]) + [request[6]] + Array(request[7..<15])
            reply += nak ? [254,255,255,255,0,0] : [0,0,0,0,UInt8(wanted & 255),UInt8(wanted >> 8)]
            writeAll(pair[1], reply)
            if stage == 3 { return }
        }
        preconditionFailure("ACK priority peer disconnected")
    }
    defer { Darwin.close(pair[0]) }
    try usb.testMuxOut(payload)
    precondition(done.wait(timeout: .now()+10) == .success)
}
try verifyAckPriority()
print("Real GuestUSB: full frame preserved across descriptor boundaries, NAK retries and short-OUT rejection passed")
