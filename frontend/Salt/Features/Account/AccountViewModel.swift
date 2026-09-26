import Combine
import SwiftUI

@MainActor
final class AccountViewModel: ObservableObject {
    @Published private(set) var profile: AccountProfile
    @Published private(set) var isWorking = false
    @Published var banner: String?

    private let session: SessionController?
    private var ticket: AnyCancellable?

    init(dataSource: any AccountDataSource) {
        profile = dataSource.loadProfile()
        session = nil
    }

    init(session: SessionController) {
        self.session = session
        profile = session.profile
        isWorking = session.isWorking
        ticket = Publishers.CombineLatest(session.$account, session.$isWorking)
            .receive(on: DispatchQueue.main)
            .sink { [weak self] account, working in
                guard let self else { return }
                if let account {
                    self.profile = AccountProfileBuilder.profile(for: account)
                }
                self.isWorking = working
            }
    }

    var canManageSession: Bool { session != nil }

    func retrySetup() {
        guard let session else { return }
        banner = nil
        Task {
            do {
                try await session.retryProvision()
            } catch {
                banner = error.localizedDescription
            }
        }
    }

    func logOut() {
        guard let session else { return }
        Task { await session.logOut() }
    }
}
