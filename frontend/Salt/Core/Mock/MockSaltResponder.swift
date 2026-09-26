enum MockSaltResponder {
    static func reply(to userText: String, items: [WardrobeItem]) -> String {
        let trimmed = userText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return MockCopy.emptyReply }

        let tokens = tokens(in: trimmed)
        let insights = WardrobeInsights(items: items)

        if contains(tokens, offerWords) {
            return insights.offerSentence()
        }
        if contains(tokens, financeWords) {
            return MockWeek.sentence()
        }
        if contains(tokens, gapWords) {
            return insights.gapSentence()
        }

        let focus = Marketplace.allCases.filter { tokens.contains($0.rawValue) }
        if contains(tokens, listingWords) || !focus.isEmpty {
            var text = insights.sentence(focusing: focus)
            if contains(tokens, priceWords) {
                text += " " + insights.priceRangeSentence(focusing: focus)
            }
            return text
        }
        if contains(tokens, greetingWords) {
            return MockCopy.greetingReply
        }
        return MockCopy.fallbackReply
    }

    private static let offerWords: Set<String> = [
        "offer", "offers", "haggle", "haggling", "discount", "discounts", "buyer", "buyers"
    ]
    private static let financeWords: Set<String> = [
        "week", "money", "report", "reports", "sold", "sales", "finance", "fee", "fees", "profit", "earnings"
    ]
    private static let gapWords: Set<String> = [
        "first", "cross", "missing", "gap", "gaps"
    ]
    private static let listingWords: Set<String> = [
        "list", "listed", "listing", "listings", "wardrobe", "live", "selling", "stock", "price", "prices", "charge"
    ]
    private static let priceWords: Set<String> = [
        "price", "prices", "charge"
    ]
    private static let greetingWords: Set<String> = [
        "hi", "hello", "hey", "hiya", "morning", "afternoon", "evening"
    ]

    private static func contains(_ tokens: Set<String>, _ words: Set<String>) -> Bool {
        !tokens.isDisjoint(with: words)
    }

    private static func tokens(in text: String) -> Set<String> {
        let parts = text.lowercased().split { character in
            !character.isLetter && !character.isNumber
        }
        return Set(parts.map(String.init))
    }
}
