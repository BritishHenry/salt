import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

enum SaltChatExchange {
    static func request(
        baseURL: URL,
        token: String,
        transcript: [ChatTurn],
        imageURL: String? = nil
    ) throws -> URLRequest {
        let messages = wireMessages(from: transcript)
        guard let last = messages.last, last.role == "user" else {
            throw AccountAPIError(message: "The last message must be from the user.")
        }
        let attached = imageURL ?? lastUserImage(in: transcript)
        var request = URLRequest(url: try AccountExchange.url(baseURL: baseURL, path: "api/agents/salt/chat"))
        request.httpMethod = "POST"
        request.timeoutInterval = 300
        request.setValue("text/event-stream", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        request.httpBody = try JSONEncoder().encode(
            SaltChatRequestBody(messages: messages, imageURL: attached)
        )
        return request
    }

    static func lastUserImage(in transcript: [ChatTurn]) -> String? {
        for turn in transcript.reversed() {
            if case .user(let message) = turn, let imageURL = message.imageURL, !imageURL.isEmpty {
                return imageURL
            }
        }
        return nil
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
    var imageURL: String?

    enum CodingKeys: String, CodingKey {
        case messages
        case imageURL = "image_url"
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(messages, forKey: .messages)
        if let imageURL, !imageURL.isEmpty {
            try container.encode(imageURL, forKey: .imageURL)
        }
    }
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
