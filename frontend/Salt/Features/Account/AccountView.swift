import SwiftUI

struct AccountView: View {
    @StateObject private var viewModel: AccountViewModel
    @Environment(\.openURL) private var openURL
    @State private var confirmingLogout = false

    init(dataSource: any AccountDataSource = MockAccountDataSource()) {
        _viewModel = StateObject(wrappedValue: AccountViewModel(dataSource: dataSource))
    }

    init(session: SessionController) {
        _viewModel = StateObject(wrappedValue: AccountViewModel(session: session))
    }

    var body: some View {
        SaltScreen {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    SaltScreenHeader(title: "Account", subtitle: "Your selling setup")
                    AccountProfileHeader(profile: viewModel.profile)
                    if let note = viewModel.profile.statusNote {
                        Text(note)
                            .font(SaltFont.body)
                            .foregroundStyle(SaltColor.cocoa)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(14)
                            .background(SaltColor.peach, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                    ForEach(viewModel.profile.sections) { section in
                        SettingsSection(section: section)
                    }
                    if viewModel.canManageSession {
                        sessionActions
                    }
                    if let banner = viewModel.banner {
                        Text(banner)
                            .font(SaltFont.body)
                            .foregroundStyle(SaltColor.cocoa)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    footer
                }
                .padding(16)
                .padding(.bottom, 12)
            }
            .accessibilityIdentifier("account.settings")
        }
        .onAppear {
            Task { await viewModel.refresh() }
        }
        .confirmationDialog("Log out of Salt?", isPresented: $confirmingLogout, titleVisibility: .visible) {
            Button("Log out", role: .destructive) {
                viewModel.logOut()
            }
            Button("Cancel", role: .cancel) {}
        }
    }

    private var sessionActions: some View {
        VStack(spacing: 12) {
            if let raw = viewModel.profile.stripeOnboardingURL, let url = URL(string: raw) {
                Button {
                    openURL(url)
                } label: {
                    Text("Finish payout setup")
                        .font(SaltFont.headline)
                        .foregroundStyle(SaltColor.onPrimary)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 52)
                        .background(SaltColor.primary, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                }
                .buttonStyle(.plain)
                .disabled(viewModel.isWorking)
                .accessibilityIdentifier("account.payouts")
            }
            if viewModel.profile.needsProvisionRetry {
                Button {
                    viewModel.retrySetup()
                } label: {
                    Text(viewModel.isWorking ? "Trying again" : "Try setup again")
                        .font(SaltFont.headline)
                        .foregroundStyle(SaltColor.cocoa)
                        .frame(maxWidth: .infinity)
                        .frame(minHeight: 52)
                        .background(SaltColor.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                        .overlay(
                            RoundedRectangle(cornerRadius: 18, style: .continuous)
                                .stroke(SaltColor.hairline, lineWidth: 1)
                        )
                }
                .buttonStyle(.plain)
                .disabled(viewModel.isWorking)
                .accessibilityIdentifier("account.retry")
            }
            Button {
                confirmingLogout = true
            } label: {
                Text("Log out")
                    .font(SaltFont.chip)
                    .foregroundStyle(SaltColor.cocoa)
                    .frame(maxWidth: .infinity)
                    .frame(minHeight: 44)
            }
            .buttonStyle(.plain)
            .disabled(viewModel.isWorking)
            .accessibilityIdentifier("account.logout")
        }
    }

    private var footer: some View {
        VStack(spacing: 8) {
            SaltMark(size: 36)
            Text("Salt is named after a cat.")
                .font(SaltFont.caption)
                .foregroundStyle(SaltColor.cocoa)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 4)
    }
}

private struct AccountProfileHeader: View {
    let profile: AccountProfile

    var body: some View {
        VStack(spacing: 8) {
            ZStack {
                Circle().fill(SaltColor.primary)
                Circle().fill(SaltColor.white).padding(5)
                Text(initials)
                    .font(SaltFont.title)
                    .foregroundStyle(SaltColor.cocoa)
            }
            .frame(width: 88, height: 88)
            .accessibilityHidden(true)

            Text(profile.displayName)
                .font(SaltFont.title)
                .foregroundStyle(SaltColor.cocoa)
            Text(profile.email)
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
            Text(profile.memberSinceLabel)
                .font(SaltFont.caption)
                .foregroundStyle(SaltColor.cocoa)
        }
        .frame(maxWidth: .infinity)
        .accessibilityElement(children: .combine)
    }

    private var initials: String {
        let parts = profile.displayName.split(separator: " ")
        let letters = parts.prefix(2).compactMap(\.first)
        return String(letters).uppercased()
    }
}

struct AccountView_Previews: PreviewProvider {
    static var previews: some View {
        AccountView()
    }
}
