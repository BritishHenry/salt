import SwiftUI

@MainActor
final class WardrobeViewModel: ObservableObject {
    @Published private(set) var load = WardrobeLoadState(items: [], isLoading: true, failure: nil)
    @Published var filter: WardrobeFilter = .all

    private let dataSource: any WardrobeDataSource
    private var reloadGeneration = 0

    init(dataSource: any WardrobeDataSource) {
        self.dataSource = dataSource
    }

    var items: [WardrobeItem] { load.items }
    var isLoading: Bool { load.isLoading }
    var failure: String? { load.failure }

    var visibleItems: [WardrobeItem] {
        filter.apply(to: items)
    }

    var subtitle: String {
        if isLoading && items.isEmpty {
            return "Loading the wardrobe."
        }
        let count = visibleItems.count
        let noun = count == 1 ? "piece" : "pieces"
        switch filter {
        case .all:
            return "\(count) \(noun)"
        case .marketplace(let marketplace):
            return "\(count) \(noun) on \(marketplace.displayName)"
        }
    }

    func chipTitle(for filter: WardrobeFilter) -> String {
        "\(filter.title) \(filter.apply(to: items).count)"
    }

    func reload() async {
        reloadGeneration += 1
        let generation = reloadGeneration
        load.started()
        do {
            let items = try await dataSource.loadItems()
            guard generation == reloadGeneration else { return }
            load.succeeded(items)
        } catch {
            guard generation == reloadGeneration else { return }
            let message = (error as? AccountAPIError)?.message ?? "Salt couldn't reach the server."
            load.failed(message)
        }
    }
}
