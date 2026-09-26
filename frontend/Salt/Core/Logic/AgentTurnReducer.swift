import Foundation

enum AgentTurnReducer {
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
            next.error = message
            next.phase = .failed
        }
        return next
    }
}
