import SwiftUI

struct WardrobeItemCard: View {
    let item: WardrobeItem

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            thumbnail
            VStack(alignment: .leading, spacing: 6) {
                Text(item.displayTitle)
                    .font(SaltFont.headline)
                    .foregroundStyle(SaltColor.cocoa)
                    .fixedSize(horizontal: false, vertical: true)
                Text(metaLine)
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.cocoa)
                HStack(alignment: .firstTextBaseline) {
                    Text(item.priceText)
                        .font(SaltFont.headline)
                        .foregroundStyle(SaltColor.cocoa)
                    Spacer(minLength: 8)
                    Text(item.conditionText)
                        .font(SaltFont.caption)
                        .foregroundStyle(SaltColor.cocoa)
                }
                MarketplaceMarks(listings: item.listings)
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

    private var metaLine: String {
        let brand = item.brand.trimmingCharacters(in: .whitespacesAndNewlines)
        let size = item.size.trimmingCharacters(in: .whitespacesAndNewlines)
        switch (brand.isEmpty, size.isEmpty) {
        case (true, true):
            return "No brand or size"
        case (false, true):
            return brand
        case (true, false):
            return "Size \(size)"
        case (false, false):
            return "\(brand) · \(size)"
        }
    }

    @ViewBuilder
    private var thumbnail: some View {
        if let photoURL = item.photoURL {
            AsyncImage(url: photoURL) { phase in
                if case .success(let image) = phase {
                    image
                        .resizable()
                        .scaledToFill()
                } else {
                    GarmentGlyph(kind: item.kind)
                }
            }
            .frame(width: 72, height: 92)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        } else {
            GarmentGlyph(kind: item.kind)
        }
    }

    private var accessibilitySummary: String {
        var parts = [
            item.displayTitle,
            metaLine,
            item.priceText,
            item.conditionText,
            item.listingDescription
        ]
        for listing in item.listings where !listing.isLive {
            if let label = listing.statusLabel {
                parts.append("\(label) on \(listing.marketplace.displayName)")
            }
        }
        if let offer = item.pendingOffer {
            let amount = MoneyFormat.gbp(pence: offer.pence)
            parts.append("Offer \(amount) on \(offer.marketplace.displayName)")
        }
        return parts.joined(separator: ". ")
    }
}
