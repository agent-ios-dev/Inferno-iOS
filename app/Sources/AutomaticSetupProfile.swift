import Foundation
import CryptoKit

/// One reproducible configuration; incompatible firmware is never tried silently.
enum AutomaticSetupProfile {
    static let id = "iphone12,1-18A5351d-v1"
    struct Asset {
        let name: String
        let url: URL
        let bytes: Int64
        let sha256: String?
    }
    static let firmware = Asset(name: "iPhone11,8,iPhone12,1_14.0_18A5351d_Restore.ipsw",
        url: URL(string: "https://updates.cdn-apple.com/2020SummerSeed/fullrestores/001-35886/5FE9BE2E-17F8-41C8-96BB-B76E2B225888/iPhone11,8,iPhone12,1_14.0_18A5351d_Restore.ipsw")!,
        bytes: 5_507_405_643, sha256: nil)
    static let ticket = Asset(name: "ticket.shsh2", url: URL(string: "https://chefkiss.dev/Extras/Inferno/ticket.shsh2")!,
        bytes: 79_421, sha256: "4380ca55889c4ddd08567496fc573f22ec6f4a66192751eee2f701913419db90")
    static let rom = Asset(name: "AppleSEPROM-Cebu-B1", url: URL(string: "https://securerom.fun/resources/SEPROM/AppleSEPROM-Cebu-B1")!,
        bytes: 86_016, sha256: "e3b11f624e3382a203c1f781b889b407554668936c86b0e2d41d229976317a1b")
    // Public firmware IV/key for this exact build, from The Apple Wiki:
    // Keys:AzulSeed_18A5351d_(iPhone12,1), SEP-Firmware. Not a device secret.
    static let sepKey = "017a328b048aab2edcc4cfe043c2d844" + "a55e67143d57938e37ec6b83ba9e181c0d24bd0a6a14f9f39752b967a9c45cfc"
    static let assets = [firmware, ticket, rom]

    enum Failure: LocalizedError {
        case invalid(String)
        var errorDescription: String? {
            if case .invalid(let what) = self { return what }; return nil
        }
    }
    static func permits(_ url: URL) -> Bool {
        guard url.scheme == "https", url.user == nil, url.password == nil,
              url.port == nil || url.port == 443, let host = url.host?.lowercased() else { return false }
        return host == "updates.cdn-apple.com" || host == "chefkiss.dev" || host == "securerom.fun"
    }

    static func validateFile(_ url: URL, asset: Asset) throws {
        let values = try url.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey])
        guard values.isRegularFile == true, values.isSymbolicLink != true,
              values.fileSize == Int(asset.bytes) else { throw Failure.invalid("Неполный файл: \(asset.name)") }
        if let expected = asset.sha256 {
            let stream = try FileHandle(forReadingFrom: url); defer { try? stream.close() }
            var hash = SHA256()
            while let chunk = try stream.read(upToCount: 1 << 20), !chunk.isEmpty { hash.update(data: chunk) }
            let actual = hash.finalize().map { String(format: "%02x", $0) }.joined()
            guard actual == expected else { throw Failure.invalid("Контрольная сумма не совпала: \(asset.name)") }
        }
    }

    static func validateManifest(_ bytes: Data) throws {
        guard let manifest = try PropertyListSerialization.propertyList(from: bytes, format: nil) as? [String: Any],
              manifest["ProductBuildVersion"] as? String == "18A5351d",
              manifest["ProductVersion"] as? String == "14.0",
              let products = manifest["SupportedProductTypes"] as? [String], products.contains("iPhone12,1"),
              let identities = manifest["BuildIdentities"] as? [[String: Any]],
              identities.contains(where: {
                  guard let info = $0["Info"] as? [String: Any] else { return false }
                  return info["DeviceClass"] as? String == "n104ap" && info["RestoreBehavior"] as? String == "Erase"
              }) else { throw Failure.invalid("Нужна iOS 14 beta 5 (18A5351d) для iPhone 11 (n104ap)") }
    }
}
