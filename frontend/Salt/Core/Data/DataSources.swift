import Foundation

/// Read seams for the three tabs.
/// Signed-in chat streams Salt's thinking and reply. A signed-in wardrobe loads and edits listings. A signed-in account loads its profile from `SignedInAccountDataSource`.
protocol ChatDataSource {
    var agentName: String { get }
    var suggestions: [String] { get }
    func loadTranscript() -> [ChatTurn]
    func makeUserTurn(text: String, at date: Date) -> ChatTurn
    func makeAgentTurn(at date: Date) -> AgentTurn
    func reply(to userText: String, in transcript: [ChatTurn]) -> AsyncStream<ChatStreamEvent>
}

protocol WardrobeDataSource {
    func loadItems() async throws -> [WardrobeItem]
    func saveItem(_ write: WardrobeItemWrite, id: String?) async throws -> WardrobeItem
    func uploadPhoto(itemID: String, filename: String, data: Data, mimeType: String) async throws
    func deletePhoto(itemID: String, position: Int) async throws
    func createListing(itemID: String, marketplace: Marketplace, priceMinor: Int?, currency: String) async throws
    func updateListing(itemID: String, marketplace: Marketplace, status: String) async throws
}

protocol AccountDataSource {
    func loadProfile() -> AccountProfile
}
