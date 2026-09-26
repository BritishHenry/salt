import Foundation

enum MockTranscript {
    static func opening(at now: Date) -> [ChatTurn] {
        let start = now.addingTimeInterval(-2 * 60 * 60)
        return [
            .agent(
                AgentTurn(
                    id: "welcome",
                    thinking: "",
                    message: MockCopy.welcome,
                    phase: .complete,
                    error: nil,
                    startedAt: start
                )
            ),
            .user(
                ChatMessage(
                    id: "seed-user",
                    author: .user,
                    text: MockCopy.seedQuestion,
                    sentAt: start.addingTimeInterval(60)
                )
            ),
            .agent(
                AgentTurn(
                    id: "seed-salt",
                    thinking: "",
                    message: WardrobeInsights(items: MockWardrobe.items).gapSentence(),
                    phase: .complete,
                    error: nil,
                    startedAt: start.addingTimeInterval(90)
                )
            )
        ]
    }
}
