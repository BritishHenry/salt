import SwiftUI

struct SaltChatHeader: View {
    let name: String

    var body: some View {
        HStack(spacing: 12) {
            SaltMark(size: 48)
            VStack(alignment: .leading, spacing: 2) {
                Text(name)
                    .font(SaltFont.headline)
                    .foregroundStyle(SaltColor.cocoa)
                Text("Your wardrobe agent")
                    .font(SaltFont.caption)
                    .foregroundStyle(SaltColor.cocoa)
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 12)
        .background(SaltColor.background)
        .overlay(alignment: .bottom) {
            Rectangle()
                .fill(SaltColor.hairline)
                .frame(height: 1)
        }
        .accessibilityElement(children: .combine)
    }
}
