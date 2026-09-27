import Foundation

enum GarmentKind: String, Codable, Hashable, Sendable {
    case top
    case bottom
    case dress
    case outerwear
    case shoes
    case bag
    case other

    static func resolve(category: String) -> GarmentKind {
        switch category {
        case "tops":
            return .top
        case "bottoms":
            return .bottom
        case "dresses":
            return .dress
        case "outerwear":
            return .outerwear
        case "shoes":
            return .shoes
        case "bags":
            return .bag
        default:
            return .other
        }
    }
}
