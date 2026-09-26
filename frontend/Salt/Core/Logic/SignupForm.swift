import Foundation

enum SignupForm {
    static func signupIssue(displayName: String, email: String, password: String) -> String? {
        let name = normalizedName(displayName)
        if name.isEmpty {
            return "Add the name you sell under."
        }
        if name.count > 255 {
            return "That name is too long."
        }
        if let emailIssue = emailIssue(email) {
            return emailIssue
        }
        if password.isEmpty {
            return "Choose a password."
        }
        return nil
    }

    static func loginIssue(email: String, password: String) -> String? {
        if let emailIssue = emailIssue(email) {
            return emailIssue
        }
        if password.isEmpty {
            return "Enter your password."
        }
        return nil
    }

    static func normalizedName(_ displayName: String) -> String {
        displayName.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    static func normalizedEmail(_ email: String) -> String {
        email.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }

    private static func emailIssue(_ email: String) -> String? {
        let value = normalizedEmail(email)
        let parts = value.split(separator: "@", omittingEmptySubsequences: false)
        let domain = parts.count == 2 ? parts[1] : ""
        let local = parts.count == 2 ? parts[0] : ""
        let valid = parts.count == 2
            && !local.isEmpty
            && domain.contains(".")
            && !domain.hasPrefix(".")
            && !domain.hasSuffix(".")
            && !value.contains(" ")
        return valid ? nil : "Enter a valid email address."
    }
}
