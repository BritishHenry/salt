import Foundation

enum MockTranscript {
    static func opening(at now: Date) -> [ChatMessage] {
        let start = now.addingTimeInterval(-2 * 60 * 60)
        return [
            ChatMessage(
                id: "welcome",
                author: .agent(name: MockCopy.agentName),
                text: MockCopy.welcome,
                sentAt: start
            ),
            ChatMessage(
                id: "seed-user",
                author: .user,
                text: MockCopy.seedQuestion,
                sentAt: start.addingTimeInterval(60)
            ),
            ChatMessage(
                id: "seed-salt",
                author: .agent(name: MockCopy.agentName),
                text: WardrobeInsights(items: MockWardrobe.items).gapSentence(),
                sentAt: start.addingTimeInterval(90)
            )
        ]
    }
}
