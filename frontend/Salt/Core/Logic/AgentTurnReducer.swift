import Foundation

enum AgentTurnReducer {
    static let unfinishedMessage = "Salt couldn't finish that. Try again."

    /// Applies one stream event. Finished turns stay as they are.
    static func apply(_ event: ChatStreamEvent, to turn: AgentTurn) -> AgentTurn {
        guard turn.phase == .thinking || turn.phase == .writing else { return turn }

        var next = turn
        switch event {
        case .thinking(let delta):
            next.thinking += delta
        case .message(let delta):
            next.message += delta
            next.phase = .writing
        case .done(let thinking, let message):
            next.thinking = thinking
            next.message = message
            next.error = nil
            next.phase = .complete
        case .error(let message):
            let note = message.trimmingCharacters(in: .whitespacesAndNewlines)
            next.error = note.isEmpty ? unfinishedMessage : note
            next.phase = .failed
        }
        return next
    }

    /// A stream that closes without `done` or `error` fails the turn so the composer unlocks.
    static func endStream(_ turn: AgentTurn) -> AgentTurn {
        guard turn.isBusy else { return turn }
        return apply(.error(unfinishedMessage), to: turn)
    }
}
