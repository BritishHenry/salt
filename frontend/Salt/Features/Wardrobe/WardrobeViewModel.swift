import SwiftUI

@MainActor
final class WardrobeViewModel: ObservableObject {
    @Published private(set) var items: [WardrobeItem]
    @Published var filter: WardrobeFilter = .all

    init(dataSource: any WardrobeDataSource) {
        items = dataSource.loadItems()
    }

    var visibleItems: [WardrobeItem] {
        filter.apply(to: items)
    }

    var subtitle: String {
        let count = visibleItems.count
        let noun = count == 1 ? "piece" : "pieces"
        switch filter {
        case .all:
            return "\(count) \(noun) listed"
        case .marketplace(let marketplace):
            return "\(count) \(noun) on \(marketplace.displayName)"
        }
    }

    func chipTitle(for filter: WardrobeFilter) -> String {
        "\(filter.title) \(filter.apply(to: items).count)"
    }
}
