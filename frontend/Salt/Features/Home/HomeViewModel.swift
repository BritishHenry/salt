import SwiftUI

@MainActor
final class HomeViewModel: ObservableObject {
    @Published private(set) var turns: [ChatTurn]
    @Published private(set) var isReplying = false

    private let dataSource: any ChatDataSource
    private var replyTask: Task<Void, Never>?

    var agentName: String { dataSource.agentName }
    var suggestions: [String] { dataSource.suggestions }

    var scrollRevision: String {
        turns.map(\.revision).joined(separator: ";")
    }

    init(dataSource: any ChatDataSource) {
        self.dataSource = dataSource
        turns = dataSource.loadTranscript()
    }

    deinit {
        replyTask?.cancel()
    }

    @discardableResult
    func send(_ rawText: String, imageURL: String? = nil) -> Bool {
        let text = rawText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isReplying else { return false }

        replyTask?.cancel()
        var user = dataSource.makeUserTurn(text: text, at: Date())
        if let imageURL, case .user(var message) = user {
            message.imageURL = imageURL
            user = .user(message)
        }
        turns.append(user)
        let transcript = turns
        let agent = dataSource.makeAgentTurn(at: Date())
        turns.append(.agent(agent))
        isReplying = true

        let agentID = agent.id
        replyTask = Task { @MainActor [weak self] in
            guard let stream = self?.dataSource.reply(to: text, in: transcript) else { return }
            for await event in stream {
                guard !Task.isCancelled, let self else { return }
                self.apply(event, to: agentID)
            }
            guard !Task.isCancelled, let self else { return }
            self.endStream(for: agentID)
        }
        return true
    }

    private func apply(_ event: ChatStreamEvent, to id: String) {
        guard let index = turns.firstIndex(where: { $0.id == id }),
              case .agent(let turn) = turns[index] else { return }
        turns[index] = .agent(AgentTurnReducer.apply(event, to: turn))
        refreshReplying()
    }

    private func endStream(for id: String) {
        guard let index = turns.firstIndex(where: { $0.id == id }),
              case .agent(let turn) = turns[index] else { return }
        turns[index] = .agent(AgentTurnReducer.endStream(turn))
        refreshReplying()
    }

    private func refreshReplying() {
        if case .agent(let turn) = turns.last {
            isReplying = turn.isBusy
        } else {
            isReplying = false
        }
    }
}

private extension ChatTurn {
    var revision: String {
        switch self {
        case .user(let message):
            return message.id
        case .agent(let turn):
            return turn.revision
        }
    }
}
