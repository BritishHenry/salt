import SwiftUI

struct WardrobeView: View {
    private let dataSource: any WardrobeDataSource
    @StateObject private var viewModel: WardrobeViewModel
    @State private var isAdding = false
    @State private var editing: WardrobeItem?

    init(dataSource: any WardrobeDataSource = MockWardrobeDataSource()) {
        self.dataSource = dataSource
        _viewModel = StateObject(wrappedValue: WardrobeViewModel(dataSource: dataSource))
    }

    var body: some View {
        SaltScreen {
            VStack(alignment: .leading, spacing: 14) {
                header
                    .padding(.horizontal, 16)
                    .padding(.top, 8)
                filters
                list
            }
            .accessibilityIdentifier("wardrobe.list")
        }
        .sheet(isPresented: $isAdding) {
            WardrobeEditorView(dataSource: dataSource, item: nil) {
                Task { await viewModel.reload() }
            }
        }
        .sheet(item: $editing) { item in
            WardrobeEditorView(dataSource: dataSource, item: item) {
                Task { await viewModel.reload() }
            }
        }
    }

    private var header: some View {
        HStack(alignment: .top, spacing: 12) {
            SaltScreenHeader(title: "Wardrobe", subtitle: viewModel.subtitle)
            Button("Add") {
                isAdding = true
            }
            .font(SaltFont.headline)
            .foregroundStyle(SaltColor.onPrimary)
            .padding(.horizontal, 16)
            .frame(minHeight: 44)
            .background(SaltColor.primary, in: Capsule())
            .accessibilityIdentifier("wardrobe.add")
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
            if viewModel.isLoading && viewModel.items.isEmpty {
                ProgressView()
                    .tint(SaltColor.primary)
                    .padding(.top, 48)
            } else if viewModel.visibleItems.isEmpty {
                emptyState
            } else {
                LazyVStack(spacing: 12) {
                    ForEach(viewModel.visibleItems) { item in
                        Button {
                            editing = item
                        } label: {
                            WardrobeItemCard(item: item)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            if viewModel.failure != nil, !viewModel.items.isEmpty {
                failureBanner
                    .padding(.horizontal, 16)
                    .padding(.bottom, 24)
            }
        }
        .refreshable {
            await viewModel.reload()
        }
        .animation(.easeInOut(duration: 0.2), value: viewModel.filter)
        .onAppear {
            Task { await viewModel.reload() }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Text(emptyTitle)
                .font(SaltFont.headline)
                .foregroundStyle(SaltColor.cocoa)
                .multilineTextAlignment(.center)
            if let failure = viewModel.failure, viewModel.items.isEmpty {
                Text(failure)
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.cocoa)
                    .multilineTextAlignment(.center)
                Button("Try again") {
                    Task { await viewModel.reload() }
                }
                .font(SaltFont.headline)
                .foregroundStyle(SaltColor.onPrimary)
                .padding(.horizontal, 16)
                .frame(minHeight: 44)
                .background(SaltColor.primary, in: Capsule())
                .accessibilityIdentifier("wardrobe.retry")
            } else {
                Text("Pieces show up here once they're listed.")
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.cocoa)
                    .multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 32)
        .padding(.top, 48)
    }

    private var failureBanner: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(viewModel.failure ?? "")
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
            Button("Try again") {
                Task { await viewModel.reload() }
            }
            .font(SaltFont.headline)
            .foregroundStyle(SaltColor.cocoa)
            .accessibilityIdentifier("wardrobe.retry")
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(14)
        .background(SaltColor.peach, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .accessibilityIdentifier("wardrobe.error")
    }

    private var emptyTitle: String {
        if viewModel.failure != nil, viewModel.items.isEmpty {
            return "Couldn't load the wardrobe"
        }
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
