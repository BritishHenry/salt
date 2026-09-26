import Foundation

struct AccountProfile: Equatable, Codable, Hashable, Sendable {
    let displayName: String
    let email: String
    let memberSinceLabel: String
    let sections: [AccountSection]
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
