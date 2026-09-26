import Foundation

final class URLSessionHTTPTransport: HTTPTransport, @unchecked Sendable {
    private let session: URLSession

    init(session: URLSession? = nil) {
        if let session {
            self.session = session
        } else {
            let configuration = URLSessionConfiguration.ephemeral
            configuration.timeoutIntervalForRequest = 60
            configuration.timeoutIntervalForResource = 90
            configuration.waitsForConnectivity = true
            self.session = URLSession(configuration: configuration)
        }
    }

    func send(_ request: URLRequest) throws -> HTTPResponse {
        var captured: Result<HTTPResponse, Error>?
        let semaphore = DispatchSemaphore(value: 0)
        let task = session.dataTask(with: request) { data, response, error in
            if let error {
                captured = .failure(AccountAPIError(message: Self.message(for: error)))
            } else if let http = response as? HTTPURLResponse {
                captured = .success(HTTPResponse(statusCode: http.statusCode, data: data ?? Data()))
            } else {
                captured = .failure(AccountAPIError(message: "Salt couldn't reach the server."))
            }
            semaphore.signal()
        }
        task.resume()
        semaphore.wait()
        guard let captured else {
            throw AccountAPIError(message: "Salt couldn't reach the server.")
        }
        return try captured.get()
    }

    private static func message(for error: Error) -> String {
        let code = (error as? URLError)?.code
        switch code {
        case .notConnectedToInternet, .cannotConnectToHost, .cannotFindHost, .timedOut, .networkConnectionLost:
            return "Salt couldn't reach the server. Check that it's running."
        default:
            return "Salt couldn't reach the server."
        }
    }
}
