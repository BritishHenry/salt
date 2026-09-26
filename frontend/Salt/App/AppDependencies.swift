/// Composition root. Chat and wardrobe stay on mock data until those APIs exist.
struct AppDependencies {
    var chat: any ChatDataSource
    var wardrobe: any WardrobeDataSource
    var account: any AccountDataSource

    static let live = AppDependencies(
        chat: MockChatDataSource(),
        wardrobe: MockWardrobeDataSource(),
        account: MockAccountDataSource()
    )

    static func signedIn(_ account: SignedInAccount) -> AppDependencies {
        AppDependencies(
            chat: MockChatDataSource(),
            wardrobe: MockWardrobeDataSource(),
            account: SignedInAccountDataSource(account: account)
        )
    }
}
