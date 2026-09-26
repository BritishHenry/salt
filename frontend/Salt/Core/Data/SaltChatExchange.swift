import Foundation

enum SaltChatServerEvent: Equatable, Sendable {
    case thinking(String)
    case message(String)
    case done(thinking: String, message: String)
    case failure(String)
}

struct SaltChatDraft: Equatable, Sendable {
    var thinking = ""
    var message = ""

    mutating func apply(_ event: SaltChatServerEvent) {
        switch event {
        case .thinking(let delta):
            thinking += delta
        case .message(let delta):
            message += delta
        case .done(let thinking, let message):
            if !thinking.isEmpty {
                self.thinking = thinking
            }
            if !message.isEmpty {
                self.message = message
            }
        case .failure(let text):
            let note = text.trimmingCharacters(in: .whitespacesAndNewlines)
            let visible = note.isEmpty ? "Salt couldn't finish that. Try again." : note
            if message.isEmpty {
                message = visible
            } else {
                message += "\n\n" + visible
            }
        }
    }
}

struct SaltChatSSEParser {
    private var buffer = ""

    mutating func append(_ text: String) -> [SaltChatServerEvent] {
        buffer += text.replacingOccurrences(of: "\r\n", with: "\n")
        var events: [SaltChatServerEvent] = []
        while let range = buffer.range(of: "\n\n") {
            let block = String(buffer[..<range.lowerBound])
            buffer = String(buffer[range.upperBound...])
            if let event = Self.event(from: block) {
                events.append(event)
            }
        }
        return events
    }

    mutating func finish() -> [SaltChatServerEvent] {
        let tail = buffer
        buffer = ""
        guard let event = Self.event(from: tail) else { return [] }
        return [event]
    }

    private static func event(from block: String) -> SaltChatServerEvent? {
        var name = ""
        var dataLines: [String] = []
        for line in block.split(separator: "\n", omittingEmptySubsequences: false) {
            let text = String(line)
            if text.hasPrefix("event:") {
                name = text.dropFirst("event:".count).trimmingCharacters(in: .whitespaces)
            } else if text.hasPrefix("data:") {
                dataLines.append(String(text.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces))
            }
        }
        guard !name.isEmpty, !dataLines.isEmpty else { return nil }
        guard let body = dataLines.joined(separator: "\n").data(using: .utf8),
              let payload = try? JSONDecoder().decode(SaltChatEventPayload.self, from: body) else {
            return nil
        }
        switch name {
        case "thinking":
            guard let delta = payload.delta, !delta.isEmpty else { return nil }
            return .thinking(delta)
        case "message":
            guard let delta = payload.delta, !delta.isEmpty else { return nil }
            return .message(delta)
        case "done":
            return .done(thinking: payload.thinking ?? "", message: payload.message ?? "")
        case "error":
            return .failure(payload.error ?? "")
        default:
            return nil
        }
    }
}

enum SaltChatExchange {
    static func request(baseURL: URL, token: String, transcript: [ChatMessage]) throws -> URLRequest {
        let messages = wireMessages(from: transcript)
        guard let last = messages.last, last.role == "user" else {
            throw AccountAPIError(message: "The last message must be from the user.")
        }
        var request = URLRequest(url: try AccountExchange.url(baseURL: baseURL, path: "api/agents/salt/chat"))
        request.httpMethod = "POST"
        request.timeoutInterval = 120
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(SaltChatRequestBody(messages: messages))
        return request
    }

    static func wireMessages(from transcript: [ChatMessage]) -> [SaltChatWireMessage] {
        transcript.compactMap { message in
            if message.id.hasPrefix("local:") {
                return nil
            }
            let content = message.text.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !content.isEmpty else { return nil }
            return SaltChatWireMessage(role: message.isFromUser ? "user" : "assistant", content: content)
        }
    }

    static func message(forHTTPError statusCode: Int, body: Data) -> String {
        if let payload = try? JSONDecoder().decode(SaltChatErrorBody.self, from: body) {
            let message = payload.error.trimmingCharacters(in: .whitespacesAndNewlines)
            if !message.isEmpty {
                return message
            }
        }
        if statusCode == 401 {
            return "Authentication required."
        }
        return "Salt couldn't finish that. Try again."
    }
}

struct SaltChatWireMessage: Equatable, Codable, Sendable {
    var role: String
    var content: String
}

private struct SaltChatRequestBody: Encodable {
    var messages: [SaltChatWireMessage]
}

private struct SaltChatEventPayload: Decodable {
    var delta: String?
    var thinking: String?
    var message: String?
    var error: String?
}

private struct SaltChatErrorBody: Decodable {
    var error: String
}

protocol SaltChatStreaming: Sendable {
    func streamReply(
        transcript: [ChatMessage],
        onEvent: @Sendable (SaltChatServerEvent) async -> Void
    ) async throws
}
