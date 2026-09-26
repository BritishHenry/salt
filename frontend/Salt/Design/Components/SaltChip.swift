import SwiftUI

struct SaltChip: View {
    let title: String
    var isSelected = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            Text(title)
                .font(SaltFont.chip)
                .foregroundStyle(isSelected ? SaltColor.onPrimary : SaltColor.ink)
                .lineLimit(1)
                .padding(.horizontal, 14)
                .frame(minHeight: 44)
                .background(isSelected ? SaltColor.primary : SaltColor.surface, in: Capsule())
                .overlay(
                    Capsule().stroke(isSelected ? Color.clear : SaltColor.hairline, lineWidth: 1)
                )
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isSelected ? .isSelected : AccessibilityTraits())
    }
}
