// Independent caption readback from actual encoded-frame PNGs on macOS.
// This is an OCR spot check per cue, not Qwen acoustic forced alignment.
import Foundation
import Vision
import AppKit

var results: [[String: Any]] = []
for filename in CommandLine.arguments.dropFirst() {
    let url = URL(fileURLWithPath: filename)
    guard let image = NSImage(contentsOf: url),
          let cg = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        throw NSError(domain: "CaptionOCR", code: 1, userInfo: [NSLocalizedDescriptionKey: "Unreadable frame: \(filename)"])
    }
    let request = VNRecognizeTextRequest()
    request.recognitionLevel = .accurate
    request.recognitionLanguages = ["zh-Hans", "en-US"]
    request.usesLanguageCorrection = false
    // Vision's rectangle is normalized from the lower-left. It includes the
    // two subtitle lines while excluding the attribution footer and city HUD.
    request.regionOfInterest = CGRect(x: 0.08, y: 0.047, width: 0.84, height: 0.095)
    try VNImageRequestHandler(cgImage: cg).perform([request])
    let observations = request.results ?? []
    let ordered = observations.sorted { $0.boundingBox.midY > $1.boundingBox.midY }
    let strings = ordered.compactMap { $0.topCandidates(1).first?.string }
    results.append(["file": filename, "text": strings])
}
let data = try JSONSerialization.data(withJSONObject: results, options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(data)
