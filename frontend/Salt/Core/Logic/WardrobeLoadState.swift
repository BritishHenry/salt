import Foundation

struct WardrobeLoadState: Equatable, Sendable {
    var items: [WardrobeItem] = []
    var isLoading = false
    var failure: String?

    mutating func started() {
        isLoading = true
        failure = nil
    }

    mutating func succeeded(_ items: [WardrobeItem]) {
        self.items = items
        isLoading = false
        failure = nil
    }

    mutating func failed(_ message: String) {
        isLoading = false
        failure = message
    }
}

enum WardrobeReload {
    static func apply(
        state: inout WardrobeLoadState,
        result: Result<[WardrobeItem], AccountAPIError>,
        generation: Int,
        current: Int
    ) {
        guard generation == current else { return }
        switch result {
        case .success(let items):
            state.succeeded(items)
        case .failure(let error):
            state.failed(error.message)
        }
    }
}
