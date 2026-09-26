import SwiftUI

struct AppGate: View {
    @StateObject private var session: SessionController

    init(session: SessionController? = nil) {
        let resolved = session ?? SessionController(
            client: HTTPAccountClient(baseURL: SaltAPI.baseURL, transport: URLSessionHTTPTransport()),
            store: UserDefaultsSessionStore()
        )
        _session = StateObject(wrappedValue: resolved)
    }

    var body: some View {
        Group {
            if let account = session.account {
                RootTabView(dependencies: .signedIn(account), session: session)
            } else {
                SignupView(session: session)
            }
        }
        .preferredColorScheme(.light)
        .task {
            await session.refresh()
        }
    }
}
