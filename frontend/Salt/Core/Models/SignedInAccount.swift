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

struct StripeAmount: Equatable, Codable, Hashable, Sendable {
    var amount: Int
    var currency: String
}

/// Available and pending minor units on the connected Stripe account.
struct StripeBalance: Equatable, Codable, Hashable, Sendable {
    var available: [StripeAmount]
    var pending: [StripeAmount]
}

/// Stripe recipient created during signup. A missing account is `status == failed`.
struct StripeProvision: Equatable, Codable, Hashable, Sendable {
    var status: String?
    var error: String?
    var sellerId: Int?
    var stripeAccountId: String?
    var transfersStatus: String?
    var onboardingUrl: String?
    var balance: StripeBalance?

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
        case balance
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

struct MarketplaceLink: Equatable, Codable, Hashable, Sendable {
    var marketplace: String
    var status: String
    var externalUsername: String
    var error: String

    enum CodingKeys: String, CodingKey {
        case marketplace
        case status
        case externalUsername = "external_username"
        case error
    }

    init(marketplace: String, status: String, externalUsername: String, error: String) {
        self.marketplace = marketplace
        self.status = status
        self.externalUsername = externalUsername
        self.error = error
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        marketplace = try container.decode(String.self, forKey: .marketplace)
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? ""
        externalUsername = try container.decodeIfPresent(String.self, forKey: .externalUsername) ?? ""
        error = try container.decodeIfPresent(String.self, forKey: .error) ?? ""
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(marketplace, forKey: .marketplace)
        try container.encode(status, forKey: .status)
        try container.encode(externalUsername, forKey: .externalUsername)
        try container.encode(error, forKey: .error)
    }
}

struct SignedInAccount: Equatable, Codable, Hashable, Sendable {
    let token: String
    let user: AccountUser
    let stripe: StripeProvision
    let browserProfile: BrowserProvision
    var marketplaces: [MarketplaceLink]

    enum CodingKeys: String, CodingKey {
        case token
        case user
        case stripe
        case browserProfile = "browser_profile"
        case marketplaces
    }

    init(
        token: String,
        user: AccountUser,
        stripe: StripeProvision,
        browserProfile: BrowserProvision,
        marketplaces: [MarketplaceLink] = []
    ) {
        self.token = token
        self.user = user
        self.stripe = stripe
        self.browserProfile = browserProfile
        self.marketplaces = marketplaces
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        token = try container.decode(String.self, forKey: .token)
        user = try container.decode(AccountUser.self, forKey: .user)
        stripe = try container.decode(StripeProvision.self, forKey: .stripe)
        browserProfile = try container.decode(BrowserProvision.self, forKey: .browserProfile)
        marketplaces = try container.decodeIfPresent([MarketplaceLink].self, forKey: .marketplaces) ?? []
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(token, forKey: .token)
        try container.encode(user, forKey: .user)
        try container.encode(stripe, forKey: .stripe)
        try container.encode(browserProfile, forKey: .browserProfile)
        try container.encode(marketplaces, forKey: .marketplaces)
    }
}
