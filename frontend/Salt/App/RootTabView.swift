import SwiftUI

struct RootTabView: View {
    private let dependencies: AppDependencies
    @State private var selection: AppTab = .home

    init(dependencies: AppDependencies = .live) {
        self.dependencies = dependencies
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
            AccountView(dataSource: dependencies.account)
                .tabItem {
                    Label {
                        Text(AppTab.account.title)
                    } icon: {
                        Image(systemName: AppTab.account.symbolName)
                    }
                }
                .tag(AppTab.account)
        }
        .tint(SaltColor.cocoa)
        .preferredColorScheme(.light)
    }
}

struct RootTabView_Previews: PreviewProvider {
    static var previews: some View {
        RootTabView()
    }
}
