import Foundation

protocol SessionStoring: AnyObject, Sendable {
    func load() -> SignedInAccount?
    func save(_ account: SignedInAccount)
    func clear()
}

final class MemorySessionStore: SessionStoring, @unchecked Sendable {
    private var account: SignedInAccount?

    func load() -> SignedInAccount? {
        account
    }

    func save(_ account: SignedInAccount) {
        self.account = account
    }

    func clear() {
        account = nil
    }
}

final class UserDefaultsSessionStore: SessionStoring, @unchecked Sendable {
    private let defaults: UserDefaults
    private let key: String

    init(defaults: UserDefaults = .standard, key: String = "salt.signedInAccount") {
        self.defaults = defaults
        self.key = key
    }

    func load() -> SignedInAccount? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? JSONDecoder().decode(SignedInAccount.self, from: data)
    }

    func save(_ account: SignedInAccount) {
        guard let data = try? JSONEncoder().encode(account) else { return }
        defaults.set(data, forKey: key)
    }

    func clear() {
        defaults.removeObject(forKey: key)
    }
}
