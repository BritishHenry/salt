enum WardrobeFilter: Hashable, Identifiable {
    case all
    case marketplace(Marketplace)

    var id: String {
        switch self {
        case .all:
            return "all"
        case .marketplace(let marketplace):
            return marketplace.rawValue
        }
    }

    var title: String {
        switch self {
        case .all:
            return "All"
        case .marketplace(let marketplace):
            return marketplace.displayName
        }
    }

    static var chips: [WardrobeFilter] {
        [.all] + Marketplace.allCases.map { .marketplace($0) }
    }

    func apply(to items: [WardrobeItem]) -> [WardrobeItem] {
        switch self {
        case .all:
            return items
        case .marketplace(let marketplace):
            return items.filter { $0.listedOn.contains(marketplace) }
        }
    }
}
