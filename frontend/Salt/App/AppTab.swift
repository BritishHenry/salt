enum AppTab: Hashable {
    case home
    case wardrobe
    case account

    var title: String {
        switch self {
        case .home:
            return "Home"
        case .wardrobe:
            return "Wardrobe"
        case .account:
            return "Account"
        }
    }

    var symbolName: String {
        switch self {
        case .home:
            return "bubble.left.and.bubble.right.fill"
        case .wardrobe:
            return "tshirt.fill"
        case .account:
            return "person.crop.circle.fill"
        }
    }
}
