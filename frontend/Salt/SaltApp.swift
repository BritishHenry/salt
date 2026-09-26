import SwiftUI

/// iOS client. Server behavior lives in `backend/`.
@main
struct SaltApp: App {
    init() {
        SaltAppearance.apply()
    }

    var body: some Scene {
        WindowGroup {
            AppGate()
        }
    }
}
