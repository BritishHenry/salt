import Foundation

enum Marketplace: String, CaseIterable, Codable, Hashable, Sendable, Identifiable {
    case vinted
    case depop
    case ebay

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .vinted:
            return "Vinted"
        case .depop:
            return "Depop"
        case .ebay:
            return "eBay"
        }
    }

    var monogram: String {
        switch self {
        case .vinted:
            return "V"
        case .depop:
            return "D"
        case .ebay:
            return "e"
        }
    }
}
