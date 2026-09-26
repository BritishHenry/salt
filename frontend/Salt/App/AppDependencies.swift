/// Composition root. Signed-in chat and wardrobe talk to Salt.
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
            chat: LiveChatDataSource(token: account.token, baseURL: SaltAPI.baseURL),
            wardrobe: LiveWardrobeDataSource(
                token: account.token,
                baseURL: SaltAPI.baseURL,
                transport: URLSessionHTTPTransport()
            ),
            account: SignedInAccountDataSource(account: account)
        )
    }
}
