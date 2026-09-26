import Foundation

enum SaltAgent {
    static let name = "Salt"
}

struct ChatMessage: Identifiable, Equatable, Codable, Hashable, Sendable {
    enum Author: Equatable, Codable, Hashable, Sendable {
        case user
        case agent(name: String)
    }

    let id: String
    let author: Author
    var text: String
    var thinking: String = ""
    var imageURL: String? = nil
    let sentAt: Date

    var isFromUser: Bool {
        if case .user = author { return true }
        return false
    }

    var authorName: String {
        switch author {
        case .user:
            return "You"
        case .agent(let name):
            return name
        }
    }
}
