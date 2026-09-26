import Foundation

enum ChatTurn: Identifiable, Equatable, Sendable {
    case user(ChatMessage)
    case agent(AgentTurn)

    var id: String {
        switch self {
        case .user(let message):
            return message.id
        case .agent(let turn):
            return turn.id
        }
    }

    var sentAt: Date {
        switch self {
        case .user(let message):
            return message.sentAt
        case .agent(let turn):
            return turn.startedAt
        }
    }
}

struct AgentTurn: Identifiable, Equatable, Sendable {
    enum Phase: Equatable, Sendable {
        case thinking
        case writing
        case complete
        case failed
    }

    let id: String
    var thinking: String
    var message: String
    var phase: Phase
    var error: String?
    let startedAt: Date

    var isBusy: Bool {
        phase == .thinking || phase == .writing
    }

    /// Changes whenever streamed text or phase changes, so the transcript can scroll in place.
    var revision: String {
        "\(id)|\(phaseToken)|\(thinking.count)|\(message.count)|\(error ?? "")"
    }

    private var phaseToken: String {
        switch phase {
        case .thinking:
            return "thinking"
        case .writing:
            return "writing"
        case .complete:
            return "complete"
        case .failed:
            return "failed"
        }
    }
}

enum ChatStreamEvent: Equatable, Sendable {
    case thinking(String)
    case message(String)
    case done(thinking: String, message: String)
    case error(String)
}
