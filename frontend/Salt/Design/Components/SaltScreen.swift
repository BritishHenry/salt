import SwiftUI

struct SaltScreen<Content: View>: View {
    private let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        NavigationStack {
            content
                .toolbar(.hidden, for: .navigationBar)
                .toolbarBackground(SaltColor.background, for: .navigationBar)
                .background(SaltColor.background.ignoresSafeArea())
        }
    }
}
