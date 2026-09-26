import SwiftUI

@MainActor
final class HomeViewModel: ObservableObject {
    @Published private(set) var messages: [ChatMessage]
    @Published private(set) var isReplying = false

    private let dataSource: any ChatDataSource

    var agentName: String { dataSource.agentName }
    var suggestions: [String] { dataSource.suggestions }
    var showsTypingIndicator: Bool {
        isReplying && messages.last?.isFromUser != false
    }

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

        if let streaming = dataSource as? any SaltChatStreaming {
            let replyID = UUID().uuidString
            let sentAt = Date()
            let draft = SaltChatDraftBox()
            Task { @MainActor [weak self] in
                do {
                    try await streaming.streamReply(transcript: transcript) { event in
                        let text = draft.apply(event)
                        await MainActor.run { [weak self] in
                            self?.show(text, replyID: replyID, sentAt: sentAt)
                        }
                    }
                } catch {
                    let message = (error as? AccountAPIError)?.message ?? "Salt couldn't reach the server."
                    let text = draft.apply(.failure(message))
                    self?.show(text, replyID: replyID, sentAt: sentAt)
                }
                self?.isReplying = false
            }
        } else {
            Task { @MainActor [weak self] in
                try? await Task.sleep(nanoseconds: 650_000_000)
                guard !Task.isCancelled, let self else { return }
                let reply = self.dataSource.reply(to: text, in: transcript, at: Date())
                self.messages.append(reply)
                self.isReplying = false
            }
        }
        return true
    }

    private func show(_ text: String, replyID: String, sentAt: Date) {
        guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
        let reply = ChatMessage(id: replyID, author: .agent(name: agentName), text: text, sentAt: sentAt)
        if let index = messages.firstIndex(where: { $0.id == replyID }) {
            messages[index] = reply
        } else {
            messages.append(reply)
        }
    }
}

private final class SaltChatDraftBox: @unchecked Sendable {
    private let lock = NSLock()
    private var draft = SaltChatDraft()

    func apply(_ event: SaltChatServerEvent) -> String {
        lock.lock()
        defer { lock.unlock() }
        draft.apply(event)
        return draft.message
    }
}
