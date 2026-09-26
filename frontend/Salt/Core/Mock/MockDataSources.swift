import Foundation

struct MockChatDataSource: ChatDataSource {
    var agentName: String { SaltAgent.name }
    var suggestions: [String] { MockCopy.suggestions }

    func loadTranscript() -> [ChatMessage] {
        MockTranscript.opening(at: Date())
    }

    func makeUserMessage(text: String, at date: Date) -> ChatMessage {
        ChatMessage(id: UUID().uuidString, author: .user, text: text, sentAt: date)
    }

    func reply(to userText: String, in _: [ChatMessage], at date: Date) -> ChatMessage {
        ChatMessage(
            id: UUID().uuidString,
            author: .agent(name: MockCopy.agentName),
            text: MockSaltResponder.reply(to: userText, items: MockWardrobe.items),
            sentAt: date
        )
    }
}

struct MockWardrobeDataSource: WardrobeDataSource {
    func loadItems() -> [WardrobeItem] {
        MockWardrobe.items
    }
}

struct MockAccountDataSource: AccountDataSource {
    func loadProfile() -> AccountProfile {
        MockAccount.profile
    }
}
