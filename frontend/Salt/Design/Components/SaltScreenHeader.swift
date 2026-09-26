import SwiftUI

struct SaltScreenHeader: View {
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(SaltFont.title)
                .foregroundStyle(SaltColor.cocoa)
                .accessibilityAddTraits(.isHeader)
            Text(subtitle)
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}
