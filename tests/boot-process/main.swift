import Foundation

func require(_ value: Bool, _ message: String) {
    guard value else { fatalError(message) }
}
let processes = BootProcessEvidence.parse("INFERNO_PS_OK|SpringBoard=123|backboardd=456\n")
require(processes?.count == 2, "Both named live guest PIDs must be retained")
require(processes?[0]["pid"] as? Int == 123, "PID must come from the response")
require(processes?[1]["name"] as? String == "backboardd", "Exact allowed name")
require(BootProcessEvidence.parse("INFERNO_PS_OK")?.isEmpty == true, "Answered absence differs from unavailable query")
for invalid in ["INFERNO_PS_UNAVAILABLE", "INFERNO_PS_ERROR", "SpringBoard is starting",
                "INFERNO_PS_OK|SpringBoard=0", "INFERNO_PS_OK|SpringBoard=-1",
                "INFERNO_PS_OK|SpringBoard=١٢٣", "INFERNO_PS_OK|SpringBoard=2147483648",
                "INFERNO_PS_OK|SpringBoard=4|backboardd=4", "INFERNO_PS_OK|unexpected=5",
                "INFERNO_PS_OK|SpringBoard=4\nprivate log", "INFERNO_PS_OK|",
                String(repeating: "x", count: 2049)] {
    require(BootProcessEvidence.parse(invalid) == nil, "Malformed, unavailable or unrelated output is not PID evidence")
}
print("Live guest process evidence parser checks passed; no guest was booted by this test.")
