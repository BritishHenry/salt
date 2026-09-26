import Foundation

struct AccountUser: Equatable, Codable, Hashable, Sendable {
    let id: Int
    let email: String
    let displayName: String

    enum CodingKeys: String, CodingKey {
        case id
        case email
        case displayName = "display_name"
    }
}

/// Stripe recipient created during signup. A missing account is `status == failed`.
struct StripeProvision: Equatable, Codable, Hashable, Sendable {
    var status: String?
    var error: String?
    var sellerId: Int?
    var stripeAccountId: String?
    var transfersStatus: String?
    var onboardingUrl: String?

    var hasAccount: Bool {
        guard let stripeAccountId else { return false }
        return !stripeAccountId.isEmpty
    }

    enum CodingKeys: String, CodingKey {
        case status
        case error
        case sellerId = "seller_id"
        case stripeAccountId = "stripe_account_id"
        case transfersStatus = "transfers_status"
        case onboardingUrl = "onboarding_url"
    }
}

/// Browser Use profile created during signup so Salt can sign in to the shops.
struct BrowserProvision: Equatable, Codable, Hashable, Sendable {
    var status: String
    var profileId: String?
    var error: String?

    var isReady: Bool {
        status == "ready" && !(profileId ?? "").isEmpty
    }

    enum CodingKeys: String, CodingKey {
        case status
        case profileId = "profile_id"
        case error
    }
}

struct SignedInAccount: Equatable, Codable, Hashable, Sendable {
    let token: String
    let user: AccountUser
    let stripe: StripeProvision
    let browserProfile: BrowserProvision

    enum CodingKeys: String, CodingKey {
        case token
        case user
        case stripe
        case browserProfile = "browser_profile"
    }
}
