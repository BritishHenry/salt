import SwiftUI

struct GarmentGlyph: View {
    let kind: GarmentKind

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(tile)
            Image(systemName: symbolName)
                .font(.system(size: 26, weight: .semibold))
                .foregroundStyle(SaltColor.cocoa)
        }
        .frame(width: 72, height: 92)
        .accessibilityHidden(true)
    }

    private var symbolName: String {
        switch kind {
        case .shoes:
            return "shoeprints.fill"
        case .bag:
            return "bag.fill"
        case .top, .bottom, .dress, .outerwear:
            return "tshirt.fill"
        }
    }

    private var tile: Color {
        switch kind {
        case .top, .dress:
            return SaltColor.peach
        case .bottom, .shoes:
            return SaltColor.lilac.opacity(0.45)
        case .outerwear, .bag:
            return SaltColor.green.opacity(0.35)
        }
    }
}
