/// v1 composition root. Swap these data sources when the backend exists.
struct AppDependencies {
    var chat: any ChatDataSource
    var wardrobe: any WardrobeDataSource
    var account: any AccountDataSource

    static let live = AppDependencies(
        chat: MockChatDataSource(),
        wardrobe: MockWardrobeDataSource(),
        account: MockAccountDataSource()
    )
}
