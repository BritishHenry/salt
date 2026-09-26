import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

struct LiveChatDataSource: ChatDataSource, SaltChatStreaming {
    var token: String
    var baseURL: URL

    var agentName: String { SaltAgent.name }
    var suggestions: [String] { MockCopy.suggestions }

    func loadTranscript() -> [ChatTurn] {
        [
            .agent(
                AgentTurn(
                    id: "local:welcome",
                    thinking: "",
                    message: "Hello, I'm Salt. Ask me about the shop.",
                    phase: .complete,
                    error: nil,
                    startedAt: Date()
                )
            )
        ]
    }

    func makeUserTurn(text: String, at date: Date) -> ChatTurn {
        .user(ChatMessage(id: UUID().uuidString, author: .user, text: text, sentAt: date))
    }

    func makeAgentTurn(at date: Date) -> AgentTurn {
        AgentTurn(
            id: UUID().uuidString,
            thinking: "",
            message: "",
            phase: .thinking,
            error: nil,
            startedAt: date
        )
    }

    func reply(to _: String, in transcript: [ChatTurn]) -> AsyncStream<ChatStreamEvent> {
        AsyncStream { continuation in
            let task = Task {
                do {
                    try await streamReply(transcript: transcript) { event in
                        continuation.yield(ChatStreamEvent(serverEvent: event))
                    }
                } catch {
                    if !Task.isCancelled {
                        let message = (error as? AccountAPIError)?.message ?? "Salt couldn't reach the server."
                        continuation.yield(.error(message))
                    }
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }

    func streamReply(
        transcript: [ChatTurn],
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

private extension ChatStreamEvent {
    init(serverEvent: SaltChatServerEvent) {
        switch serverEvent {
        case .thinking(let delta):
            self = .thinking(delta)
        case .message(let delta):
            self = .message(delta)
        case .done(let thinking, let message):
            self = .done(thinking: thinking, message: message)
        case .failure(let text):
            let note = text.trimmingCharacters(in: .whitespacesAndNewlines)
            self = .error(note.isEmpty ? "Salt couldn't finish that. Try again." : note)
        }
    }
}
