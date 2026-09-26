import Foundation

struct PendingOffer: Equatable, Codable, Hashable, Sendable {
    let pence: Int
    let marketplace: Marketplace
}

struct WardrobeItem: Identifiable, Equatable, Codable, Hashable, Sendable {
    let id: String
    let title: String
    let brand: String
    let size: String
    let condition: String
    let pricePence: Int
    let kind: GarmentKind
    let listedOn: Set<Marketplace>
    let pendingOffer: PendingOffer?

    var listingDescription: String {
        let listed = Marketplace.allCases.filter { listedOn.contains($0) }.map(\.displayName)
        let unlisted = Marketplace.allCases.filter { !listedOn.contains($0) }.map(\.displayName)
        var parts: [String] = []
        if !listed.isEmpty {
            parts.append("Listed on \(ListPhrase.join(listed))")
        }
        if !unlisted.isEmpty {
            parts.append("Not listed on \(ListPhrase.join(unlisted))")
        }
        guard !parts.isEmpty else { return "Not listed." }
        return parts.joined(separator: ". ") + "."
    }
}
