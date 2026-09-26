import Foundation

/// Read seams for the three tabs. Chat and wardrobe still use the mock types.
/// A signed-in account loads its profile from `SignedInAccountDataSource`.
protocol ChatDataSource {
    var agentName: String { get }
    var suggestions: [String] { get }
    func loadTranscript() -> [ChatTurn]
    func makeUserTurn(text: String, at date: Date) -> ChatTurn
    func makeAgentTurn(at date: Date) -> AgentTurn
    func reply(to userText: String, in transcript: [ChatTurn]) -> AsyncStream<ChatStreamEvent>
}

protocol WardrobeDataSource {
    func loadItems() -> [WardrobeItem]
}

protocol AccountDataSource {
    func loadProfile() -> AccountProfile
}
