import Foundation

enum MockSaltStream {
    static let thinkingText = "Checking the wardrobe."

    static func events(for userText: String) -> [ChatStreamEvent] {
        let reply = MockSaltResponder.reply(to: userText, items: MockWardrobe.items)
        let (first, second) = messageDeltas(in: reply)
        return [
            .thinking(thinkingText),
            .message(first),
            .message(second),
            .done(thinking: thinkingText, message: reply)
        ]
    }

    private static func messageDeltas(in reply: String) -> (String, String) {
        guard reply.count > 1 else { return (reply, "") }
        let midpoint = reply.index(reply.startIndex, offsetBy: reply.count / 2)
        if let space = reply[..<midpoint].lastIndex(of: " ") {
            let cut = reply.index(after: space)
            return (String(reply[..<cut]), String(reply[cut...]))
        }
        return (String(reply[..<midpoint]), String(reply[midpoint...]))
    }
}

struct MockChatDataSource: ChatDataSource {
    var agentName: String { SaltAgent.name }
    var suggestions: [String] { MockCopy.suggestions }

    func loadTranscript() -> [ChatTurn] {
        MockTranscript.opening(at: Date())
    }

    func makeUserTurn(text: String, at date: Date) -> ChatTurn {
        .user(ChatMessage(id: UUID().uuidString, author: .user, text: text, sentAt: date))
    }

    func makeAgentTurn(at date: Date) -> AgentTurn {
        AgentTurn(
            id: UUID().uuidString,
            thinking: "",
            message: "",
            phase: .thinking,
            error: nil,
            startedAt: date
        )
    }

    func reply(to userText: String, in _: [ChatTurn]) -> AsyncStream<ChatStreamEvent> {
        let events = MockSaltStream.events(for: userText)
        return AsyncStream { continuation in
            let task = Task {
                for event in events {
                    do {
                        try await Task.sleep(nanoseconds: 320_000_000)
                    } catch {
                        break
                    }
                    continuation.yield(event)
                }
                continuation.finish()
            }
            continuation.onTermination = { _ in
                task.cancel()
            }
        }
    }
}

struct MockWardrobeDataSource: WardrobeDataSource {
    func loadItems() async throws -> [WardrobeItem] {
        MockWardrobe.items
    }

    func saveItem(_ write: WardrobeItemWrite, id: String?) async throws -> WardrobeItem {
        WardrobeItem(
            id: id ?? "mock-new",
            title: write.title,
            brand: write.brand,
            size: write.sizeLabel,
            condition: write.condition,
            pricePence: write.priceMinor,
            currency: write.currency,
            kind: GarmentKind.resolve(category: write.category),
            category: write.category
        )
    }

    func uploadPhoto(itemID _: String, filename _: String, data _: Data, mimeType _: String) async throws {}

    func deletePhoto(itemID _: String, position _: Int) async throws {}

    func createListing(
        itemID _: String,
        marketplace _: Marketplace,
        priceMinor _: Int?,
        currency _: String
    ) async throws {}

    func updateListing(itemID _: String, marketplace _: Marketplace, status _: String) async throws {}
}

struct MockAccountDataSource: AccountDataSource {
    func loadProfile() -> AccountProfile {
        MockAccount.profile
    }
}
