import SwiftUI

struct WardrobeItemCard: View {
    let item: WardrobeItem

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            GarmentGlyph(kind: item.kind)
            VStack(alignment: .leading, spacing: 6) {
                Text(item.title)
                    .font(SaltFont.headline)
                    .foregroundStyle(SaltColor.cocoa)
                    .fixedSize(horizontal: false, vertical: true)
                Text("\(item.brand) · \(item.size)")
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.cocoa)
                HStack(alignment: .firstTextBaseline) {
                    Text(MoneyFormat.gbp(pence: item.pricePence))
                        .font(SaltFont.headline)
                        .foregroundStyle(SaltColor.cocoa)
                    Spacer(minLength: 8)
                    Text(item.condition)
                        .font(SaltFont.caption)
                        .foregroundStyle(SaltColor.cocoa)
                }
                MarketplaceMarks(listedOn: item.listedOn)
                if let offer = item.pendingOffer {
                    Text("Offer \(MoneyFormat.gbp(pence: offer.pence)) on \(offer.marketplace.displayName)")
                        .font(SaltFont.caption.weight(.semibold))
                        .foregroundStyle(SaltColor.cocoa)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 4)
                        .background(SaltColor.primarySoft, in: Capsule())
                }
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(SaltColor.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .stroke(SaltColor.hairline, lineWidth: 1)
        )
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilitySummary)
    }

    private var accessibilitySummary: String {
        var parts = [
            item.title,
            "\(item.brand), size \(item.size)",
            MoneyFormat.gbp(pence: item.pricePence),
            item.condition,
            item.listingDescription
        ]
        if let offer = item.pendingOffer {
            let amount = MoneyFormat.gbp(pence: offer.pence)
            parts.append("Offer \(amount) on \(offer.marketplace.displayName)")
        }
        return parts.joined(separator: ". ")
    }
}
