import Foundation
import CryptoKit

func require(_ condition: @autoclosure () -> Bool, _ reason: String) {
    if !condition() { fatalError(reason) }
}
func refuses(_ reason: String, _ operation: () throws -> Void) {
    do { try operation() } catch { return }
    fatalError(reason)
}

let profile = AutomaticSetupProfile.self
require(profile.permits(profile.firmware.url), "official IPSW must be permitted")
for text in ["http://updates.cdn-apple.com/a", "https://updates.cdn-apple.com.evil.test/a",
             "https://chefkiss.dev:444/a", "https://user:password@chefkiss.dev/a", "file:///tmp/a"] {
    require(!profile.permits(URL(string: text)!), "untrusted redirect accepted")
}
var manifest: [String: Any] = ["ProductBuildVersion": "18A5351d", "ProductVersion": "14.0",
    "SupportedProductTypes": ["iPhone11,8", "iPhone12,1"],
    "BuildIdentities": [["Info": ["DeviceClass": "n104ap", "RestoreBehavior": "Erase"]]]]
func encode(_ object: Any) throws -> Data {
    try PropertyListSerialization.data(fromPropertyList: object, format: .xml, options: 0)
}
try profile.validateManifest(encode(manifest))
manifest["ProductBuildVersion"] = "18A373"
refuses("wrong build accepted with the SEP key for beta 5") { try profile.validateManifest(encode(manifest)) }
manifest["ProductBuildVersion"] = "18A5351d"
manifest["BuildIdentities"] = [["Info": ["DeviceClass": "n104ap", "RestoreBehavior": "Update"]]]
refuses("update identity accepted for erase restore") { try profile.validateManifest(encode(manifest)) }
let folder = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: folder) }
let file = folder.appendingPathComponent("input"), link = folder.appendingPathComponent("link")
try Data("abc".utf8).write(to: file)
let asset = AutomaticSetupProfile.Asset(name: "fixture", url: profile.ticket.url, bytes: 3,
    sha256: "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
try profile.validateFile(file, asset: asset)
try Data("abd".utf8).write(to: file)
refuses("same-size corrupt download accepted") { try profile.validateFile(file, asset: asset) }
try Data("ab".utf8).write(to: file)
refuses("truncated download accepted") { try profile.validateFile(file, asset: asset) }
try FileManager.default.createSymbolicLink(at: link, withDestinationURL: file)
refuses("symlink accepted as cached firmware") { try profile.validateFile(link, asset: asset) }
require(profile.sepKey.count == 96 && profile.sepKey.allSatisfy(\.isHexDigit), "invalid fixed SEP key format")
print("Automatic setup: manifest identity, redirect trust, file integrity, truncation and symlink checks passed")
