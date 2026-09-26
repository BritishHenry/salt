import SwiftUI

struct WardrobeView: View {
    @StateObject private var viewModel: WardrobeViewModel

    init(dataSource: any WardrobeDataSource = MockWardrobeDataSource()) {
        _viewModel = StateObject(wrappedValue: WardrobeViewModel(dataSource: dataSource))
    }

    var body: some View {
        SaltScreen {
            VStack(alignment: .leading, spacing: 14) {
                SaltScreenHeader(title: "Wardrobe", subtitle: viewModel.subtitle)
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                filters
                list
            }
            .accessibilityIdentifier("wardrobe.list")
        }
    }

    private var filters: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(WardrobeFilter.chips) { filter in
                    SaltChip(
                        title: viewModel.chipTitle(for: filter),
                        isSelected: viewModel.filter == filter
                    ) {
                        viewModel.filter = filter
                    }
                }
            }
            .padding(.horizontal, 16)
        }
    }

    private var list: some View {
        ScrollView {
            if viewModel.visibleItems.isEmpty {
                emptyState
            } else {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.visibleItems) { item in
                        WardrobeItemCard(item: item)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
        }
        .animation(.easeInOut(duration: 0.2), value: viewModel.filter)
    }

    private var emptyState: some View {
        VStack(spacing: 8) {
            Text(emptyTitle)
                .font(SaltFont.headline)
                .foregroundStyle(SaltColor.cocoa)
                .multilineTextAlignment(.center)
            Text("Pieces show up here once they're listed.")
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 32)
        .padding(.top, 48)
    }

    private var emptyTitle: String {
        switch viewModel.filter {
        case .all:
            return "The wardrobe is empty"
        case .marketplace(let marketplace):
            return "Nothing on \(marketplace.displayName) yet"
        }
    }
}

struct WardrobeView_Previews: PreviewProvider {
    static var previews: some View {
        WardrobeView()
    }
}
