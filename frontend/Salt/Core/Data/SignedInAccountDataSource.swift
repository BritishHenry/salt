import Foundation

struct SignedInAccountDataSource: AccountDataSource {
    var account: SignedInAccount

    func loadProfile() -> AccountProfile {
        AccountProfileBuilder.profile(for: account)
    }
}
