import Foundation

struct PendingOffer: Equatable, Codable, Hashable, Sendable {
    let pence: Int
    let marketplace: Marketplace
}

struct WardrobePhoto: Equatable, Codable, Hashable, Sendable {
    var position: Int
    var url: URL?
}

struct WardrobeListing: Equatable, Codable, Hashable, Sendable {
    var marketplace: Marketplace
    var status: String

    var isLive: Bool { status == "live" }

    var statusLabel: String? {
        switch status {
        case "live", "":
            return nil
        case "draft":
            return "Draft"
        case "publishing":
            return "Publishing"
        case "paused":
            return "Paused"
        case "sold":
            return "Sold"
        case "ended":
            return "Ended"
        case "failed":
            return "Failed"
        default:
            return status.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }
}

struct WardrobeItem: Identifiable, Equatable, Codable, Hashable, Sendable {
    let id: String
    let title: String
    let brand: String
    let size: String
    let condition: String
    let pricePence: Int?
    let currency: String
    let kind: GarmentKind
    let category: String
    let listings: [WardrobeListing]
    let pendingOffer: PendingOffer?
    let photos: [WardrobePhoto]

    init(
        id: String,
        title: String,
        brand: String,
        size: String,
        condition: String,
        pricePence: Int?,
        currency: String = "gbp",
        kind: GarmentKind,
        category: String = "",
        listedOn: Set<Marketplace> = [],
        listings: [WardrobeListing] = [],
        pendingOffer: PendingOffer? = nil,
        photos: [WardrobePhoto] = []
    ) {
        self.id = id
        self.title = title
        self.brand = brand
        self.size = size
        self.condition = condition
        self.pricePence = pricePence
        self.currency = currency
        self.kind = kind
        self.category = category
        if listings.isEmpty {
            self.listings = Marketplace.allCases
                .filter { listedOn.contains($0) }
                .map { WardrobeListing(marketplace: $0, status: "live") }
        } else {
            self.listings = listings
        }
        self.pendingOffer = pendingOffer
        self.photos = photos
    }

    /// Marketplaces whose listing status is live.
    var listedOn: Set<Marketplace> {
        Set(listings.filter(\.isLive).map(\.marketplace))
    }

    var displayTitle: String {
        let trimmed = title.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? "Untitled" : trimmed
    }

    var priceText: String {
        guard let pricePence else { return "No price" }
        return MoneyFormat.amount(minor: pricePence, currency: currency)
    }

    var conditionText: String {
        WardrobeTaxonomy.conditionLabel(condition)
    }

    var photoURL: URL? {
        photos.sorted { $0.position < $1.position }.compactMap(\.url).first
    }

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
