import Foundation

/// Read seams for the three tabs. Wardrobe still uses the mock type.
/// Signed-in chat streams Salt's thinking and reply. A signed-in account loads its profile from `SignedInAccountDataSource`.
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
