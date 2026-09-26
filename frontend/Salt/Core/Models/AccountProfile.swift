import Foundation

struct AccountProfile: Equatable, Codable, Hashable, Sendable {
    let displayName: String
    let email: String
    let memberSinceLabel: String
    let sections: [AccountSection]
    var stripeOnboardingURL: String? = nil
    var needsProvisionRetry: Bool = false
    var statusNote: String? = nil
}

struct AccountSection: Identifiable, Equatable, Codable, Hashable, Sendable {
    let id: String
    let title: String
    let rows: [AccountRow]
}

struct AccountRow: Identifiable, Equatable, Codable, Hashable, Sendable {
    let id: String
    let title: String
    let value: String
}
