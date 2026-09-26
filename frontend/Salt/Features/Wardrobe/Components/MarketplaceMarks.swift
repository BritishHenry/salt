import SwiftUI

struct MarketplaceMarks: View {
    let listedOn: Set<Marketplace>

    var body: some View {
        WrappingHStack(horizontalSpacing: 6, verticalSpacing: 6) {
            ForEach(Marketplace.allCases) { marketplace in
                mark(for: marketplace, listed: listedOn.contains(marketplace))
            }
        }
        .accessibilityHidden(true)
    }

    private func mark(for marketplace: Marketplace, listed: Bool) -> some View {
        let style = MarkStyle.resolve(marketplace: marketplace, listed: listed)
        return HStack(spacing: 4) {
            if listed {
                Image(systemName: "checkmark")
                    .font(.system(size: 9, weight: .bold))
            }
            Text(marketplace.displayName)
                .font(SaltFont.caption.weight(.semibold))
        }
        .foregroundStyle(style.foreground)
        .padding(.horizontal, 8)
        .padding(.vertical, 5)
        .background(style.fill, in: Capsule())
        .overlay(Capsule().stroke(style.stroke, lineWidth: 1))
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
                fill: SaltColor.green.opacity(0.35),
                stroke: SaltColor.green,
                foreground: SaltColor.cocoa
            )
        case .depop:
            return MarkStyle(
                fill: SaltColor.lilac.opacity(0.4),
                stroke: SaltColor.lilac,
                foreground: SaltColor.cocoa
            )
        case .ebay:
            return MarkStyle(
                fill: SaltColor.peach,
                stroke: SaltColor.cocoa.opacity(0.28),
                foreground: SaltColor.cocoa
            )
        }
    }
}
