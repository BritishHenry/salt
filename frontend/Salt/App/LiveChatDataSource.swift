import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

struct LiveChatDataSource: ChatDataSource, SaltChatStreaming {
    var token: String
    var baseURL: URL

    var agentName: String { SaltAgent.name }
    var suggestions: [String] { MockCopy.suggestions }

    func loadTranscript() -> [ChatMessage] {
        [
            ChatMessage(
                id: "local:welcome",
                author: .agent(name: agentName),
                text: "Hello, I'm Salt. Ask me about the shop.",
                sentAt: Date()
            )
        ]
    }

    func makeUserMessage(text: String, at date: Date) -> ChatMessage {
        ChatMessage(id: UUID().uuidString, author: .user, text: text, sentAt: date)
    }

    func reply(to _: String, in _: [ChatMessage], at date: Date) -> ChatMessage {
        ChatMessage(
            id: UUID().uuidString,
            author: .agent(name: agentName),
            text: "I couldn't reach the server.",
            sentAt: date
        )
    }

    func streamReply(
        transcript: [ChatMessage],
        onEvent: @Sendable (SaltChatServerEvent) async -> Void
    ) async throws {
        let request = try SaltChatExchange.request(baseURL: baseURL, token: token, transcript: transcript)
        try await URLSessionSaltChat.stream(request, onEvent: onEvent)
    }
}

enum URLSessionSaltChat {
    static func stream(
        _ request: URLRequest,
        onEvent: @Sendable (SaltChatServerEvent) async -> Void
    ) async throws {
        let session = URLSession(configuration: configuration)
        do {
            let (bytes, response) = try await session.bytes(for: request)
            guard let http = response as? HTTPURLResponse else {
                throw AccountAPIError(message: "Salt couldn't reach the server.")
            }
            if !(200...299).contains(http.statusCode) {
                let body = try await collect(bytes, limit: 16_384)
                throw AccountAPIError(
                    message: SaltChatExchange.message(forHTTPError: http.statusCode, body: body),
                    statusCode: http.statusCode
                )
            }
            var parser = SaltChatSSEParser()
            for try await line in bytes.lines {
                for event in parser.append(line + "\n") {
                    await onEvent(event)
                }
            }
            for event in parser.finish() {
                await onEvent(event)
            }
        } catch let error as AccountAPIError {
            throw error
        } catch {
            throw AccountAPIError(message: message(for: error))
        }
    }

    private static var configuration: URLSessionConfiguration {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.timeoutIntervalForRequest = 120
        configuration.timeoutIntervalForResource = 180
        configuration.waitsForConnectivity = true
        return configuration
    }

    private static func collect(_ bytes: URLSession.AsyncBytes, limit: Int) async throws -> Data {
        var data = Data()
        for try await byte in bytes {
            data.append(byte)
            if data.count >= limit {
                break
            }
        }
        return data
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
