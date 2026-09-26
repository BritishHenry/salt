import Foundation

@MainActor
final class SessionController: ObservableObject {
    @Published private(set) var account: SignedInAccount?
    @Published private(set) var isWorking = false

    private let client: any AccountClient
    private let store: any SessionStoring

    init(client: any AccountClient, store: any SessionStoring) {
        self.client = client
        self.store = store
        account = store.load()
    }

    var profile: AccountProfile {
        guard let account else {
            return AccountProfile(displayName: "", email: "", memberSinceLabel: "", sections: [])
        }
        return AccountProfileBuilder.profile(for: account)
    }

    func signUp(displayName: String, email: String, password: String) async throws {
        if let issue = SignupForm.signupIssue(displayName: displayName, email: email, password: password) {
            throw AccountAPIError(message: issue)
        }
        let client = self.client
        try await perform {
            try client.signUp(displayName: displayName, email: email, password: password)
        }
    }

    func logIn(email: String, password: String) async throws {
        if let issue = SignupForm.loginIssue(email: email, password: password) {
            throw AccountAPIError(message: issue)
        }
        let client = self.client
        try await perform {
            try client.logIn(email: email, password: password)
        }
    }

    func retryProvision() async throws {
        guard let token = account?.token else { return }
        let client = self.client
        try await perform {
            try client.provision(token: token)
        }
    }

    func refresh() async {
        guard let token = account?.token, !isWorking else { return }
        let client = self.client
        do {
            let updated = try await Self.offMain {
                try client.currentAccount(token: token)
            }
            store.save(updated)
            account = updated
        } catch let error as AccountAPIError where error.statusCode == 401 {
            store.clear()
            account = nil
        } catch {
            return
        }
    }

    func logOut() async {
        let token = account?.token
        let client = self.client
        if let token {
            isWorking = true
            try? await Self.offMain {
                try client.logOut(token: token)
            }
            isWorking = false
        }
        store.clear()
        account = nil
    }

    private func perform(_ work: @escaping @Sendable () throws -> SignedInAccount) async throws {
        if isWorking { return }
        isWorking = true
        defer { isWorking = false }
        let updated = try await Self.offMain(work)
        store.save(updated)
        account = updated
    }

    private static func offMain<T: Sendable>(_ work: @escaping @Sendable () throws -> T) async throws -> T {
        try await withCheckedThrowingContinuation { continuation in
            DispatchQueue.global(qos: .userInitiated).async {
                continuation.resume(with: Result(catching: work))
            }
        }
    }
}
