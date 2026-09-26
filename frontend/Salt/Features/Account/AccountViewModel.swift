import SwiftUI

@MainActor
final class AccountViewModel: ObservableObject {
    @Published private(set) var profile: AccountProfile

    init(dataSource: any AccountDataSource) {
        profile = dataSource.loadProfile()
    }
}
