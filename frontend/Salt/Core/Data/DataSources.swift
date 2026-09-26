import Foundation

/// Read seams for the three tabs. Wardrobe still uses the mock type.
/// Signed-in chat streams from Salt. A signed-in account loads its profile from `SignedInAccountDataSource`.
protocol ChatDataSource {
    var agentName: String { get }
    var suggestions: [String] { get }
    func loadTranscript() -> [ChatMessage]
    func makeUserMessage(text: String, at date: Date) -> ChatMessage
    func reply(to userText: String, in transcript: [ChatMessage], at date: Date) -> ChatMessage
}

protocol WardrobeDataSource {
    func loadItems() -> [WardrobeItem]
}

protocol AccountDataSource {
    func loadProfile() -> AccountProfile
}
