import SwiftUI

struct ChatComposer: View {
    @Binding var draft: String
    var canSend: Bool
    var onSend: () -> Void

    var body: some View {
        HStack(alignment: .bottom, spacing: 8) {
            TextField(
                "Message Salt",
                text: $draft,
                prompt: Text("Message Salt").foregroundColor(SaltColor.cocoa.opacity(0.72))
            )
            .font(SaltFont.body)
            .foregroundStyle(SaltColor.cocoa)
            .textInputAutocapitalization(.sentences)
            .submitLabel(.send)
            .onSubmit(onSend)
            .padding(.horizontal, 16)
            .frame(minHeight: 44)
            .background(SaltColor.surface, in: Capsule())
            .overlay(Capsule().stroke(SaltColor.hairline, lineWidth: 1))

            Button(action: onSend) {
                Image(systemName: "arrow.up")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundStyle(SaltColor.cocoa)
                    .frame(width: 44, height: 44)
                    .background(canSend ? SaltColor.green : SaltColor.surface, in: Circle())
                    .overlay(
                        Circle().stroke(canSend ? Color.clear : SaltColor.hairline, lineWidth: 1)
                    )
            }
            .buttonStyle(.plain)
            .disabled(!canSend)
            .accessibilityLabel("Send message")
        }
        .padding(.horizontal, 16)
        .accessibilityIdentifier("chat.composer")
    }
}
