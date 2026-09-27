import Foundation

struct WardrobeChoice: Equatable, Hashable, Sendable, Identifiable {
    var code: String
    var label: String

    var id: String { code.isEmpty ? "unset" : code }
}

enum WardrobeTaxonomy {
    static let categories: [WardrobeChoice] = [
        WardrobeChoice(code: "", label: "Not set"),
        WardrobeChoice(code: "tops", label: "Tops"),
        WardrobeChoice(code: "bottoms", label: "Bottoms"),
        WardrobeChoice(code: "dresses", label: "Dresses"),
        WardrobeChoice(code: "outerwear", label: "Outerwear"),
        WardrobeChoice(code: "shoes", label: "Shoes"),
        WardrobeChoice(code: "bags", label: "Bags"),
        WardrobeChoice(code: "accessories", label: "Accessories"),
        WardrobeChoice(code: "activewear", label: "Activewear"),
        WardrobeChoice(code: "other", label: "Other")
    ]

    static let conditions: [WardrobeChoice] = [
        WardrobeChoice(code: "", label: "Not set"),
        WardrobeChoice(code: "new_with_tags", label: "New with tags"),
        WardrobeChoice(code: "new_without_tags", label: "New without tags"),
        WardrobeChoice(code: "very_good", label: "Very good"),
        WardrobeChoice(code: "good", label: "Good"),
        WardrobeChoice(code: "satisfactory", label: "Satisfactory")
    ]

    static func categoryLabel(_ code: String) -> String {
        label(for: code, in: categories)
    }

    static func conditionLabel(_ code: String) -> String {
        label(for: code, in: conditions)
    }

    private static func label(for code: String, in choices: [WardrobeChoice]) -> String {
        if let match = choices.first(where: { $0.code == code }) {
            return match.label
        }
        return code
    }
}
