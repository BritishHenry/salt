import SwiftUI

@MainActor
final class HomeViewModel: ObservableObject {
    @Published private(set) var messages: [ChatMessage]
    @Published private(set) var isReplying = false

    private let dataSource: any ChatDataSource

    var agentName: String { dataSource.agentName }
    var suggestions: [String] { dataSource.suggestions }

    init(dataSource: any ChatDataSource) {
        self.dataSource = dataSource
        messages = dataSource.loadTranscript()
    }

    @discardableResult
    func send(_ rawText: String) -> Bool {
        let text = rawText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isReplying else { return false }

        messages.append(dataSource.makeUserMessage(text: text, at: Date()))
        isReplying = true
        let transcript = messages

        Task { @MainActor [weak self] in
            try? await Task.sleep(nanoseconds: 650_000_000)
            guard !Task.isCancelled, let self else { return }
            let reply = self.dataSource.reply(to: text, in: transcript, at: Date())
            self.messages.append(reply)
            self.isReplying = false
        }
        return true
    }
}
