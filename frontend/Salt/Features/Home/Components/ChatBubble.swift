import SwiftUI

struct ChatBubble: View {
    let text: String
    let isFromUser: Bool
    let authorName: String
    let sentAt: Date
    var showsMark: Bool = true

    var body: some View {
        if isFromUser {
            HStack(alignment: .bottom, spacing: 8) {
                Spacer(minLength: 40)
                bubble(fill: SaltColor.green)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(authorName) said \(text), \(timeText)")
        } else if showsMark {
            HStack(alignment: .bottom, spacing: 8) {
                SaltMark(size: 28)
                bubble(fill: SaltColor.surface)
                Spacer(minLength: 40)
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(authorName) said \(text), \(timeText)")
        } else {
            bubble(fill: SaltColor.surface)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(authorName) said \(text), \(timeText)")
        }
    }

    private func bubble(fill: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(text)
                .font(SaltFont.body)
                .foregroundStyle(isFromUser ? SaltColor.onPrimary : SaltColor.ink)
                .multilineTextAlignment(.leading)
                .lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
            Text(timeText)
                .font(SaltFont.caption)
                .foregroundStyle(isFromUser ? SaltColor.onPrimary.opacity(0.85) : SaltColor.inkMuted)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(fill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(isFromUser ? Color.clear : SaltColor.hairline, lineWidth: 1)
        )
    }

    private var timeText: String {
        sentAt.formatted(date: .omitted, time: .shortened)
    }
}
