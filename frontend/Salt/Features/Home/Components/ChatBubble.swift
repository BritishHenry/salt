import SwiftUI

struct ChatBubble: View {
    let message: ChatMessage

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            if message.isFromUser {
                Spacer(minLength: 40)
                bubble(fill: SaltColor.green)
            } else {
                SaltMark(size: 28)
                bubble(fill: SaltColor.surface)
                Spacer(minLength: 40)
            }
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(message.authorName) said \(message.text), \(timeText)")
    }

    private func bubble(fill: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(message.text)
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
                .multilineTextAlignment(.leading)
                .lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
                .textSelection(.enabled)
            Text(timeText)
                .font(SaltFont.caption)
                .foregroundStyle(SaltColor.cocoa)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
        .background(fill, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(message.isFromUser ? Color.clear : SaltColor.hairline, lineWidth: 1)
        )
    }

    private var timeText: String {
        message.sentAt.formatted(date: .omitted, time: .shortened)
    }
}
