import PhotosUI
import SwiftUI
import UIKit
import UniformTypeIdentifiers

struct WardrobeEditorView: View {
    private let dataSource: any WardrobeDataSource
    private let startingItem: WardrobeItem?
    private let onSaved: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var persistedID: String?
    @State private var title: String
    @State private var brand: String
    @State private var size: String
    @State private var condition: String
    @State private var category: String
    @State private var priceText: String
    @State private var liveChannels: Set<Marketplace>
    @State private var pickerItem: PhotosPickerItem?
    @State private var pendingPhoto: Data?
    @State private var removePhoto = false
    @State private var errorMessage: String?
    @State private var isSaving = false
    @State private var baselinePhotos: [WardrobePhoto]

    init(dataSource: any WardrobeDataSource, item: WardrobeItem?, onSaved: @escaping () -> Void) {
        self.dataSource = dataSource
        startingItem = item
        self.onSaved = onSaved
        _baselinePhotos = State(initialValue: item?.photos ?? [])
        _persistedID = State(initialValue: item?.id)
        _title = State(initialValue: item?.title ?? "")
        _brand = State(initialValue: item?.brand ?? "")
        _size = State(initialValue: item?.size ?? "")
        _condition = State(initialValue: item?.condition ?? "")
        _category = State(initialValue: item?.category ?? "")
        _priceText = State(initialValue: MoneyParse.text(fromMinor: item?.pricePence))
        _liveChannels = State(initialValue: item?.listedOn ?? [])
    }

    var body: some View {
        SaltScreen {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    SaltScreenHeader(title: persistedID == nil ? "Add a piece" : "Edit piece", subtitle: "Save it to the wardrobe.")
                    field(title: "Title", text: $title, prompt: "Wool coat")
                    field(title: "Brand", text: $brand, prompt: "COS")
                    field(title: "Size", text: $size, prompt: "M")
                    menu(title: "Condition", value: WardrobeTaxonomy.conditionLabel(condition), choices: WardrobeTaxonomy.conditions) {
                        condition = $0
                    }
                    menu(title: "Category", value: WardrobeTaxonomy.categoryLabel(category), choices: WardrobeTaxonomy.categories) {
                        category = $0
                    }
                    field(title: "Price", text: $priceText, prompt: "28 or 28.50", keyboard: .decimalPad)
                    photoSection
                    channelSection
                    if let errorMessage {
                        Text(errorMessage)
                            .font(SaltFont.body)
                            .foregroundStyle(SaltColor.cocoa)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(14)
                            .background(SaltColor.peach, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                    }
                    saveButton
                    Button("Cancel") { dismiss() }
                        .font(SaltFont.body)
                        .foregroundStyle(SaltColor.cocoa)
                        .frame(maxWidth: .infinity, minHeight: 44)
                }
                .padding(16)
                .padding(.bottom, 12)
            }
            .accessibilityIdentifier("wardrobe.editor")
        }
    }

    private var photoSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Photo")
                .font(SaltFont.caption.weight(.semibold))
                .foregroundStyle(SaltColor.cocoa)
            if let photoURL = startingItem?.photoURL, pendingPhoto == nil, !removePhoto {
                AsyncImage(url: photoURL) { phase in
                    if case .success(let image) = phase {
                        image.resizable().scaledToFill()
                    } else {
                        Color.clear
                    }
                }
                .frame(width: 72, height: 92)
                .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            if pendingPhoto != nil {
                Text("New photo ready")
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.cocoa)
                Button("Clear new photo") {
                    pendingPhoto = nil
                    pickerItem = nil
                }
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
                .frame(minHeight: 44)
            } else if removePhoto {
                Text("Photo will be removed")
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.cocoa)
            }
            PhotosPicker(selection: $pickerItem, matching: .images) {
                Text(startingItem?.photoURL == nil ? "Add photo" : "Replace photo")
                    .font(SaltFont.headline)
                    .foregroundStyle(SaltColor.cocoa)
                    .frame(maxWidth: .infinity, minHeight: 44)
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(SaltColor.hairline, lineWidth: 1)
                    )
            }
            .onChange(of: pickerItem) { newItem in
                Task { await loadPhoto(newItem) }
            }
            if startingItem?.photos.isEmpty == false {
                Button(removePhoto ? "Keep photo" : "Remove photo") {
                    removePhoto.toggle()
                    if removePhoto {
                        pendingPhoto = nil
                        pickerItem = nil
                    }
                }
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
                .frame(minHeight: 44)
            }
        }
    }

    private var channelSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Marketplaces")
                .font(SaltFont.caption.weight(.semibold))
                .foregroundStyle(SaltColor.cocoa)
            Text("Live shows the checkmark. Turning a live channel off pauses it.")
                .font(SaltFont.body)
                .foregroundStyle(SaltColor.cocoa)
            ForEach(Marketplace.allCases) { marketplace in
                Toggle(isOn: liveBinding(marketplace)) {
                    Text(marketplace.displayName)
                        .font(SaltFont.body)
                        .foregroundStyle(SaltColor.cocoa)
                }
                .tint(SaltColor.primary)
            }
        }
    }

    private var saveButton: some View {
        Button(action: save) {
            ZStack {
                Text("Save")
                    .font(SaltFont.headline)
                    .opacity(isSaving ? 0 : 1)
                if isSaving {
                    ProgressView()
                        .tint(SaltColor.onPrimary)
                }
            }
            .foregroundStyle(SaltColor.onPrimary)
            .frame(maxWidth: .infinity, minHeight: 52)
            .background(SaltColor.primary, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .disabled(isSaving)
        .accessibilityIdentifier("wardrobe.save")
    }

    private func field(
        title: String,
        text: Binding<String>,
        prompt: String,
        keyboard: UIKeyboardType = .default
    ) -> some View {
        TextField(
            title,
            text: text,
            prompt: Text(prompt).foregroundColor(SaltColor.cocoa.opacity(0.72))
        )
        .font(SaltFont.body)
        .foregroundStyle(SaltColor.cocoa)
        .textInputAutocapitalization(keyboard == .decimalPad ? .never : .words)
        .autocorrectionDisabled()
        .keyboardType(keyboard)
        .padding(.horizontal, 16)
        .frame(minHeight: 52)
        .background(SaltColor.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(SaltColor.hairline, lineWidth: 1)
        )
        .accessibilityIdentifier("wardrobe.field.\(title.lowercased())")
    }

    private func menu(
        title: String,
        value: String,
        choices: [WardrobeChoice],
        select: @escaping (String) -> Void
    ) -> some View {
        Menu {
            ForEach(choices) { choice in
                Button(choice.label) { select(choice.code) }
            }
        } label: {
            HStack {
                Text(title)
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.cocoa)
                Spacer()
                Text(value)
                    .font(SaltFont.body.weight(.semibold))
                    .foregroundStyle(SaltColor.cocoa)
            }
            .padding(.horizontal, 16)
            .frame(minHeight: 52)
            .background(SaltColor.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(SaltColor.hairline, lineWidth: 1)
            )
        }
    }

    private func liveBinding(_ marketplace: Marketplace) -> Binding<Bool> {
        Binding(
            get: { liveChannels.contains(marketplace) },
            set: { isLive in
                if isLive {
                    liveChannels.insert(marketplace)
                } else {
                    liveChannels.remove(marketplace)
                }
            }
        )
    }

    private func loadPhoto(_ item: PhotosPickerItem?) async {
        guard let item else { return }
        if let picked = try? await item.loadTransferable(type: PickedPhoto.self), !picked.data.isEmpty {
            pendingPhoto = picked.data
            removePhoto = false
        }
    }

    private func save() {
        let parsed = MoneyParse.parse(priceText)
        if case .invalid = parsed {
            errorMessage = "Enter a price like 28 or 28.50."
            return
        }
        let priceMinor: Int?
        if case .amount(let minor) = parsed {
            priceMinor = minor
        } else {
            priceMinor = nil
        }
        let write = WardrobeItemWrite(
            title: title.trimmingCharacters(in: .whitespacesAndNewlines),
            brand: brand.trimmingCharacters(in: .whitespacesAndNewlines),
            sizeLabel: size.trimmingCharacters(in: .whitespacesAndNewlines),
            condition: condition,
            category: category,
            priceMinor: priceMinor,
            currency: startingItem?.currency ?? "gbp"
        )
        errorMessage = nil
        isSaving = true
        Task {
            do {
                try await commit(write)
                onSaved()
                dismiss()
            } catch {
                onSaved()
                errorMessage = (error as? AccountAPIError)?.message ?? "Salt couldn't finish that. Try again."
                isSaving = false
            }
        }
    }

    private func commit(_ write: WardrobeItemWrite) async throws {
        let saved = try await dataSource.saveItem(write, id: persistedID)
        persistedID = saved.id
        try await applyPhoto(itemID: saved.id)
        try await applyChannels(itemID: saved.id, priceMinor: write.priceMinor, currency: write.currency)
    }

    private func applyPhoto(itemID: String) async throws {
        let existing = baselinePhotos.sorted { $0.position < $1.position }.first
        if let pendingPhoto {
            let uploadedPosition = (baselinePhotos.map(\.position).max()).map { $0 + 1 } ?? 0
            try await dataSource.uploadPhoto(
                itemID: itemID,
                filename: "photo.jpg",
                data: pendingPhoto,
                mimeType: "image/jpeg"
            )
            if let existing {
                try await dataSource.deletePhoto(itemID: itemID, position: existing.position)
                baselinePhotos.removeAll { $0.position == existing.position }
            }
            baselinePhotos.append(WardrobePhoto(position: uploadedPosition, url: nil))
            return
        }
        if removePhoto, let existing {
            try await dataSource.deletePhoto(itemID: itemID, position: existing.position)
            baselinePhotos.removeAll { $0.position == existing.position }
        }
    }

    private func applyChannels(itemID: String, priceMinor: Int?, currency: String) async throws {
        let steps = WardrobeSavePlan.channelSteps(
            existing: startingItem?.listings ?? [],
            desiredLive: liveChannels
        )
        for step in steps {
            switch step {
            case .makeLive(let marketplace, let creating):
                if creating {
                    do {
                        try await dataSource.createListing(
                            itemID: itemID,
                            marketplace: marketplace,
                            priceMinor: priceMinor,
                            currency: currency
                        )
                    } catch let error as AccountAPIError where error.statusCode == 409 {
                    }
                }
                try await dataSource.updateListing(
                    itemID: itemID,
                    marketplace: marketplace,
                    status: "live"
                )
            case .pause(let marketplace):
                try await dataSource.updateListing(
                    itemID: itemID,
                    marketplace: marketplace,
                    status: "paused"
                )
            }
        }
    }
}

private struct PickedPhoto: Transferable {
    var data: Data

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(importedContentType: .jpeg) { data in
            PickedPhoto(data: data)
        }
    }
}
