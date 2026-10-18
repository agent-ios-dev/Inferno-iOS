import Foundation

/// URLSession streams the IPSW to a temporary file, never through a Data buffer.
final class AutomaticSetupDownload: NSObject, URLSessionDownloadDelegate, @unchecked Sendable {
    private let asset: AutomaticSetupProfile.Asset
    private let destination: URL
    private let progress: @Sendable (Double) -> Void
    private var continuation: CheckedContinuation<URL, Error>?
    private var session: URLSession?
    private var task: URLSessionDownloadTask?
    private var result: Result<URL, Error>?
    private let lock = NSLock()
    private var lastProgress: TimeInterval = 0

    init(asset: AutomaticSetupProfile.Asset, destination: URL, progress: @escaping @Sendable (Double) -> Void) {
        self.asset = asset; self.destination = destination; self.progress = progress
    }
    func run() async throws -> URL {
        try await withCheckedThrowingContinuation { continuation in
            lock.lock()
            self.continuation = continuation
            let config = URLSessionConfiguration.default
            config.timeoutIntervalForRequest = 120
            config.timeoutIntervalForResource = 7200
            config.waitsForConnectivity = true
            let session = URLSession(configuration: config, delegate: self, delegateQueue: nil)
            self.session = session
            var request = URLRequest(url: asset.url)
            request.setValue("Inferno-iOS-AutoSetup/1.0", forHTTPHeaderField: "User-Agent")
            request.setValue("identity", forHTTPHeaderField: "Accept-Encoding")
            let transfer = session.downloadTask(with: request)
            task = transfer
            lock.unlock()
            transfer.resume()
        }
    }
    func cancel() {
        lock.lock(); let transfer = task; lock.unlock()
        transfer?.cancel()
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping (URLRequest?) -> Void) {
        completionHandler(request.url.map(AutomaticSetupProfile.permits) == true ? request : nil)
    }
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didWriteData bytesWritten: Int64,
                    totalBytesWritten: Int64, totalBytesExpectedToWrite: Int64) {
        if totalBytesWritten > asset.bytes { downloadTask.cancel(); return }
        let now = Date.timeIntervalSinceReferenceDate
        if now - lastProgress >= 0.15 || totalBytesWritten == asset.bytes {
            lastProgress = now
            progress(min(1, Double(totalBytesWritten) / Double(asset.bytes)))
        }
    }
    func urlSession(_ session: URLSession, downloadTask: URLSessionDownloadTask, didFinishDownloadingTo location: URL) {
        do {
            guard let response = downloadTask.response as? HTTPURLResponse, response.statusCode == 200,
                  let url = response.url, AutomaticSetupProfile.permits(url) else { throw URLError(.badServerResponse) }
            try AutomaticSetupProfile.validateFile(location, asset: asset)
            try FileManager.default.moveItem(at: location, to: destination)
            result = .success(destination)
        } catch { result = .failure(error) }
    }
    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        let outcome = error.map { Result<URL, Error>.failure($0) } ?? result ?? .failure(URLError(.unknown))
        lock.lock()
        let waiting = continuation; continuation = nil
        self.session = nil; self.task = nil
        lock.unlock()
        session.finishTasksAndInvalidate()
        waiting?.resume(with: outcome)
    }
}
