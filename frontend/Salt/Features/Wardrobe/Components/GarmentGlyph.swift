import SwiftUI

struct GarmentGlyph: View {
    let kind: GarmentKind

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(tile)
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(SaltColor.hairline, lineWidth: 1)
                )
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
            return "shoe.fill"
        case .bag:
            return "bag.fill"
        case .top, .bottom, .dress, .outerwear:
            return "tshirt.fill"
        case .other:
            return "tag.fill"
        }
    }

    private var tile: Color {
        switch kind {
        case .top, .dress:
            return SaltColor.primarySoft
        case .bottom, .shoes:
            return SaltColor.white
        case .outerwear, .bag, .other:
            return SaltColor.primary.opacity(0.22)
        }
    }
}
