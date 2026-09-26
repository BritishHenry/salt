import SwiftUI

struct RootTabView: View {
    private let dependencies: AppDependencies
    private let session: SessionController?
    @State private var selection: AppTab = .home

    init(dependencies: AppDependencies = .live, session: SessionController? = nil) {
        self.dependencies = dependencies
        self.session = session
        SaltAppearance.apply()
    }

    var body: some View {
        TabView(selection: $selection) {
            HomeView(dataSource: dependencies.chat)
                .tabItem {
                    Label {
                        Text(AppTab.home.title)
                    } icon: {
                        Image(systemName: AppTab.home.symbolName)
                    }
                }
                .tag(AppTab.home)
            WardrobeView(dataSource: dependencies.wardrobe)
                .tabItem {
                    Label {
                        Text(AppTab.wardrobe.title)
                    } icon: {
                        Image(systemName: AppTab.wardrobe.symbolName)
                    }
                }
                .tag(AppTab.wardrobe)
            accountTab
                .tabItem {
                    Label {
                        Text(AppTab.account.title)
                    } icon: {
                        Image(systemName: AppTab.account.symbolName)
                    }
                }
                .tag(AppTab.account)
        }
        .tint(SaltColor.primary)
        .preferredColorScheme(.light)
    }

    @ViewBuilder
    private var accountTab: some View {
        if let session {
            AccountView(session: session)
        } else {
            AccountView(dataSource: dependencies.account)
        }
    }
}

struct RootTabView_Previews: PreviewProvider {
    static var previews: some View {
        RootTabView()
    }
}
