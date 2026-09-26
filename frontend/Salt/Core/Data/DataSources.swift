import Foundation

/// Read seams for the three tabs. v1 uses the mock types in `Mock`.
/// A backend client can conform to these without changing the screens.
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
