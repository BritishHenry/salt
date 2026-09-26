import SwiftUI

struct AccountView: View {
    @StateObject private var viewModel: AccountViewModel

    init(dataSource: any AccountDataSource = MockAccountDataSource()) {
        _viewModel = StateObject(wrappedValue: AccountViewModel(dataSource: dataSource))
    }

    var body: some View {
        SaltScreen {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    SaltScreenHeader(title: "Account", subtitle: "Your selling setup")
                    AccountProfileHeader(profile: viewModel.profile)
                    ForEach(viewModel.profile.sections) { section in
                        SettingsSection(section: section)
                    }
                    footer
                }
                .padding(16)
                .padding(.bottom, 12)
            }
            .accessibilityIdentifier("account.settings")
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
                Circle().fill(SaltColor.lilac)
                Circle().fill(SaltColor.peach).padding(5)
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
