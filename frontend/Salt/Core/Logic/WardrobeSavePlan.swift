import Foundation

struct WardrobeItemWrite: Equatable, Sendable {
    var title: String
    var brand: String
    var sizeLabel: String
    var condition: String
    var category: String
    var priceMinor: Int?
    var currency: String

    func jsonData() throws -> Data {
        var object: [String: Any] = [
            "title": title,
            "brand": brand,
            "size_label": sizeLabel,
            "condition": condition,
            "category": category,
            "currency": currency
        ]
        if let priceMinor {
            object["price_minor"] = priceMinor
        } else {
            object["price_minor"] = NSNull()
        }
        return try JSONSerialization.data(withJSONObject: object)
    }
}

enum WardrobeChannelStep: Equatable, Sendable {
    case makeLive(Marketplace, creating: Bool)
    case pause(Marketplace)
}

enum MoneyParse {
    enum Result: Equatable {
        case empty
        case invalid
        case amount(Int)
    }

    static func parse(_ text: String) -> Result {
        var trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return .empty }
        trimmed = trimmed.replacingOccurrences(of: "£", with: "")
        trimmed = trimmed.replacingOccurrences(of: ",", with: "")
        trimmed = trimmed.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return .empty }
        let parts = trimmed.split(separator: ".", omittingEmptySubsequences: false).map(String.init)
        guard parts.count == 1 || parts.count == 2 else { return .invalid }
        guard isDigits(parts[0]), let pounds = Int(parts[0]), pounds >= 0 else { return .invalid }
        if pounds > Int.max / 100 { return .invalid }
        if parts.count == 1 {
            return .amount(pounds * 100)
        }
        let fraction = parts[1]
        guard fraction.count <= 2, isDigits(fraction) || fraction.isEmpty == false else { return .invalid }
        guard !fraction.isEmpty, fraction.allSatisfy(\.isNumber) else { return .invalid }
        let padded = fraction.count == 1 ? fraction + "0" : fraction
        guard let pence = Int(padded) else { return .invalid }
        return .amount(pounds * 100 + pence)
    }

    static func text(fromMinor minor: Int?) -> String {
        guard let minor else { return "" }
        let pounds = minor / 100
        let remainder = abs(minor % 100)
        if remainder == 0 {
            return String(pounds)
        }
        let remainderText = remainder < 10 ? "0\(remainder)" : "\(remainder)"
        return "\(pounds).\(remainderText)"
    }

    private static func isDigits(_ text: String) -> Bool {
        !text.isEmpty && text.allSatisfy(\.isNumber)
    }
}

enum WardrobeSavePlan {
    static func channelSteps(
        existing: [WardrobeListing],
        desiredLive: Set<Marketplace>
    ) -> [WardrobeChannelStep] {
        Marketplace.allCases.compactMap { marketplace in
            let listing = existing.first { $0.marketplace == marketplace }
            let wantLive = desiredLive.contains(marketplace)
            if wantLive {
                if listing?.isLive == true { return nil }
                return .makeLive(marketplace, creating: listing == nil)
            }
            if listing?.isLive == true {
                return .pause(marketplace)
            }
            return nil
        }
    }
}
