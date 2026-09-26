import SwiftUI

struct MarketplaceMarks: View {
    let listings: [WardrobeListing]

    var body: some View {
        WrappingHStack(horizontalSpacing: 6, verticalSpacing: 6) {
            ForEach(Marketplace.allCases) { marketplace in
                mark(for: marketplace, listing: listings.first { $0.marketplace == marketplace })
            }
        }
        .accessibilityHidden(true)
    }

    private func mark(for marketplace: Marketplace, listing: WardrobeListing?) -> some View {
        let style = MarkStyle.resolve(marketplace: marketplace, listed: listing?.isLive == true)
        return HStack(spacing: 4) {
            if listing?.isLive == true {
                Image(systemName: "checkmark")
                    .font(.system(size: 9, weight: .bold))
            }
            Text(label(for: marketplace, listing: listing))
                .font(SaltFont.caption.weight(.semibold))
        }
        .foregroundStyle(style.foreground)
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(style.fill, in: Capsule())
        .overlay(Capsule().stroke(style.stroke, lineWidth: 1))
    }

    private func label(for marketplace: Marketplace, listing: WardrobeListing?) -> String {
        guard let listing, !listing.isLive, let status = listing.statusLabel else {
            return marketplace.displayName
        }
        return "\(marketplace.displayName) \(status)"
    }
}

private struct MarkStyle {
    let fill: Color
    let stroke: Color
    let foreground: Color

    static func resolve(marketplace: Marketplace, listed: Bool) -> MarkStyle {
        guard listed else {
            return MarkStyle(
                fill: SaltColor.surface,
                stroke: SaltColor.hairline,
                foreground: SaltColor.cocoa
            )
        }
        switch marketplace {
        case .vinted:
            return MarkStyle(
                fill: SaltColor.primary,
                stroke: SaltColor.primary,
                foreground: SaltColor.onPrimary
            )
        case .depop:
            return MarkStyle(
                fill: SaltColor.primarySoft,
                stroke: SaltColor.primary,
                foreground: SaltColor.ink
            )
        case .ebay:
            return MarkStyle(
                fill: SaltColor.white,
                stroke: SaltColor.primary,
                foreground: SaltColor.ink
            )
        }
    }
}
