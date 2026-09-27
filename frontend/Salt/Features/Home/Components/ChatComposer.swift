import PhotosUI
import SwiftUI
import UIKit

struct ChatComposer: View {
    @Binding var draft: String
    @Binding var attachment: String?
    var canSend: Bool
    var onSend: () -> Void
    @State private var pickerItem: PhotosPickerItem?

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if attachment != nil {
                HStack(spacing: 8) {
                    Image(systemName: "photo")
                        .foregroundStyle(SaltColor.cocoa)
                    Text("Photo attached")
                        .font(SaltFont.caption)
                        .foregroundStyle(SaltColor.cocoa)
                    Spacer()
                    Button("Remove") { attachment = nil }
                        .font(SaltFont.caption)
                        .foregroundStyle(SaltColor.cocoa)
                }
                .accessibilityIdentifier("chat.attachment")
            }
            controls
        }
        .padding(.horizontal, 16)
        .accessibilityIdentifier("chat.composer")
    }

    private var controls: some View {
        HStack(alignment: .bottom, spacing: 8) {
            PhotosPicker(selection: $pickerItem, matching: .images) {
                Image(systemName: "photo")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundStyle(SaltColor.cocoa)
                    .frame(width: 44, height: 44)
                    .background(SaltColor.surface, in: Circle())
                    .overlay(Circle().stroke(SaltColor.hairline, lineWidth: 1))
            }
            .buttonStyle(.plain)
            .accessibilityLabel("Add photo")
            .onChange(of: pickerItem) { item in
                guard let item else { return }
                Task {
                    if let data = try? await item.loadTransferable(type: Data.self),
                       let url = ChatPhoto.jpegDataURL(from: data) {
                        attachment = url
                    }
                }
            }

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
                    .foregroundStyle(canSend ? SaltColor.onPrimary : SaltColor.inkMuted)
                    .frame(width: 44, height: 44)
                    .background(canSend ? SaltColor.primary : SaltColor.surface, in: Circle())
                    .overlay(
                        Circle().stroke(canSend ? Color.clear : SaltColor.hairline, lineWidth: 1)
                    )
            }
            .buttonStyle(.plain)
            .disabled(!canSend)
            .accessibilityLabel("Send message")
        }
    }
}

enum ChatPhoto {
    /// JPEG small enough that the base64 chat body stays under Django's upload limit.
    static func jpegDataURL(from data: Data) -> String? {
        guard var image = UIImage(data: data) else { return nil }
        let maxBytes = 1_200_000
        let longest = max(image.size.width, image.size.height)
        if longest > 1600 {
            let scale = 1600 / longest
            let size = CGSize(width: image.size.width * scale, height: image.size.height * scale)
            let renderer = UIGraphicsImageRenderer(size: size)
            image = renderer.image { _ in
                image.draw(in: CGRect(origin: .zero, size: size))
            }
        }
        var quality: CGFloat = 0.85
        var jpeg = image.jpegData(compressionQuality: quality) ?? Data()
        while jpeg.count > maxBytes && quality > 0.35 {
            quality -= 0.1
            jpeg = image.jpegData(compressionQuality: quality) ?? jpeg
        }
        guard !jpeg.isEmpty, jpeg.count <= maxBytes else { return nil }
        return "data:image/jpeg;base64," + jpeg.base64EncodedString()
    }
}
