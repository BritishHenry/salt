import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

enum SaltChatExchange {
    static func request(baseURL: URL, token: String, transcript: [ChatTurn]) throws -> URLRequest {
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

    static func wireMessages(from transcript: [ChatTurn]) -> [SaltChatWireMessage] {
        transcript.compactMap { turn in
            if turn.id.hasPrefix("local:") {
                return nil
            }
            switch turn {
            case .user(let message):
                let content = message.text.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !content.isEmpty else { return nil }
                return SaltChatWireMessage(role: "user", content: content)
            case .agent(let agent):
                let content = agent.message.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !content.isEmpty else { return nil }
                return SaltChatWireMessage(role: "assistant", content: content)
            }
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
        return AgentTurnReducer.unfinishedMessage
    }

    static func openingTurn(at date: Date) -> ChatTurn {
        .agent(
            AgentTurn(
                id: "local:welcome",
                thinking: "",
                message: MockCopy.welcome,
                phase: .complete,
                error: nil,
                startedAt: date
            )
        )
    }
}

struct SaltChatWireMessage: Equatable, Codable, Sendable {
    var role: String
    var content: String
}

private struct SaltChatRequestBody: Encodable {
    var messages: [SaltChatWireMessage]
}

private struct SaltChatErrorBody: Decodable {
    var error: String
}

protocol SaltChatStreaming: Sendable {
    func streamReply(
        transcript: [ChatTurn],
        onEvent: @Sendable (ChatStreamEvent) async -> Void
    ) async throws
}
