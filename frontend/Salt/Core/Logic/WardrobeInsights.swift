struct WardrobeInsights {
    let items: [WardrobeItem]

    func count(on marketplace: Marketplace) -> Int {
        items.filter { $0.listedOn.contains(marketplace) }.count
    }

    func sentence(focusing marketplaces: [Marketplace]) -> String {
        let unique = Marketplace.allCases.filter { marketplaces.contains($0) }
        if unique.isEmpty || unique.count == Marketplace.allCases.count {
            return coverageSentence()
        }
        if unique.count == 1, let marketplace = unique.first {
            return singleMarketplaceSentence(marketplace)
        }
        let parts = unique.map { "\(count(on: $0)) on \($0.displayName)" }
        return "\(ListPhrase.join(parts))."
    }

    func coverageSentence() -> String {
        let parts = Marketplace.allCases.map { "\(count(on: $0)) on \($0.displayName)" }
        return "\(Self.countPhrase(items.count)) listed. \(ListPhrase.join(parts))."
    }

    func gapSentence() -> String {
        let singles = items.filter { $0.listedOn.count == 1 }
        guard !singles.isEmpty else {
            return "Every piece is already on at least two sites."
        }
        if singles.count == 1, let item = singles.first {
            return "The easiest win is the \(item.title), which is only on \(siteName(for: item))."
        }
        let clauses = singles.prefix(3).map { item in
            "the \(item.title) is only on \(siteName(for: item))"
        }
        let sentence = ListPhrase.join(Array(clauses)).capitalisingFirstLetter()
        return "The easiest wins are the pieces on a single site. \(sentence)."
    }

    func offerSentence() -> String {
        let offers = items.compactMap { item -> (WardrobeItem, PendingOffer)? in
            guard let offer = item.pendingOffer else { return nil }
            return (item, offer)
        }
        guard !offers.isEmpty else {
            return "Nothing has an offer waiting."
        }
        if offers.count == 1, let (item, offer) = offers.first {
            let amount = MoneyFormat.gbp(pence: offer.pence)
            let asking = item.pricePence.map { MoneyFormat.gbp(pence: $0) } ?? "no price"
            return "There's an offer on the \(item.title): \(amount) on \(offer.marketplace.displayName), against \(asking) asking. I won't reply to buyers on my own yet."
        }
        let parts = offers.map { item, offer in
            let amount = MoneyFormat.gbp(pence: offer.pence)
            return "the \(item.title) (\(amount) on \(offer.marketplace.displayName))"
        }
        return "There are offers on \(ListPhrase.join(parts)). I won't reply to buyers on my own yet."
    }

    func priceRangeSentence(focusing marketplaces: [Marketplace]) -> String {
        let prices = scopedItems(focusing: marketplaces).compactMap(\.pricePence)
        guard let low = prices.min(), let high = prices.max() else {
            return "There are no asking prices to show."
        }
        if low == high {
            return "The asking price is \(MoneyFormat.gbp(pence: low))."
        }
        let lowText = MoneyFormat.gbp(pence: low)
        let highText = MoneyFormat.gbp(pence: high)
        return "Asking prices run from \(lowText) to \(highText)."
    }

    private func scopedItems(focusing marketplaces: [Marketplace]) -> [WardrobeItem] {
        let focus = Marketplace.allCases.filter { marketplaces.contains($0) }
        guard !focus.isEmpty else { return items }
        return items.filter { item in
            focus.contains { item.listedOn.contains($0) }
        }
    }

    private func singleMarketplaceSentence(_ marketplace: Marketplace) -> String {
        let matching = items.filter { $0.listedOn.contains(marketplace) }
        guard !matching.isEmpty else {
            return "Nothing is on \(marketplace.displayName) yet."
        }
        let names = ListPhrase.join(matching.prefix(2).map(\.title))
        return "\(Self.countPhrase(matching.count)) on \(marketplace.displayName), including \(names)."
    }

    private func siteName(for item: WardrobeItem) -> String {
        Marketplace.allCases.first { item.listedOn.contains($0) }?.displayName ?? "one site"
    }

    private static func countPhrase(_ count: Int) -> String {
        count == 1 ? "1 piece is" : "\(count) pieces are"
    }
}

private extension String {
    func capitalisingFirstLetter() -> String {
        guard let first else { return self }
        return String(first).uppercased() + dropFirst()
    }
}
