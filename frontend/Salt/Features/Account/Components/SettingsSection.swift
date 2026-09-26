import SwiftUI

struct SettingsSection: View {
    let section: AccountSection

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(section.title)
                .font(SaltFont.caption.weight(.semibold))
                .foregroundStyle(SaltColor.cocoa)
                .padding(.leading, 4)
                .accessibilityAddTraits(.isHeader)
            VStack(spacing: 0) {
                ForEach(Array(section.rows.enumerated()), id: \.element.id) { index, row in
                    rowView(row)
                    if index < section.rows.count - 1 {
                        Rectangle()
                            .fill(SaltColor.hairline)
                            .frame(height: 1)
                            .padding(.leading, 58)
                    }
                }
            }
            .background(SaltColor.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .stroke(SaltColor.hairline, lineWidth: 1)
            )
        }
    }

    private func rowView(_ row: AccountRow) -> some View {
        HStack(alignment: .center, spacing: 12) {
            badge(for: row)
            Text(row.title)
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
                .layoutPriority(1)
            Spacer(minLength: 12)
            Text(row.value)
                .font(SaltFont.body.weight(.semibold))
                .foregroundStyle(SaltColor.cocoa)
                .multilineTextAlignment(.trailing)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .accessibilityElement(children: .combine)
    }

    private func badge(for row: AccountRow) -> some View {
        ZStack {
            Circle().fill(badgeColor(for: row.id))
            if let marketplace = Marketplace(rawValue: row.id) {
                Text(marketplace.monogram)
                    .font(SaltFont.caption.weight(.bold))
                    .foregroundStyle(SaltColor.cocoa)
            } else {
                Image(systemName: symbolName(for: row.id))
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(SaltColor.cocoa)
            }
        }
        .frame(width: 32, height: 32)
        .accessibilityHidden(true)
    }

    private func badgeColor(for rowID: String) -> Color {
        switch Marketplace(rawValue: rowID) {
        case .vinted:
            return SaltColor.green.opacity(0.35)
        case .depop:
            return SaltColor.lilac.opacity(0.45)
        case .ebay:
            return SaltColor.peach
        case nil:
            return SaltColor.peach
        }
    }

    private func symbolName(for rowID: String) -> String {
        switch rowID {
        case "name":
            return "person.fill"
        case "email":
            return "envelope.fill"
        case "currency":
            return "banknote"
        case "location":
            return "mappin"
        case "offers", "summary":
            return "bell.fill"
        case "version":
            return "info.circle.fill"
        default:
            return "circle.fill"
        }
    }
}
