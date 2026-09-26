import SwiftUI

struct TypingIndicator: View {
    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            SaltMark(size: 28)
            TimelineView(.periodic(from: .now, by: 0.35)) { context in
                let phase = Int(context.date.timeIntervalSinceReferenceDate / 0.35) % 3
                HStack(spacing: 5) {
                    ForEach(0..<3, id: \.self) { index in
                        Circle()
                            .fill(SaltColor.cocoa.opacity(index == phase ? 0.9 : 0.28))
                            .frame(width: 7, height: 7)
                    }
                }
                .padding(.horizontal, 14)
                .padding(.vertical, 14)
                .background(SaltColor.primarySoft, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                .overlay(
                    RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(SaltColor.hairline, lineWidth: 1)
                )
            }
            Spacer(minLength: 40)
        }
        .accessibilityLabel("Salt is thinking")
    }
}
