import Foundation

enum AccountProfileBuilder {
    static func profile(for account: SignedInAccount) -> AccountProfile {
        let stripeReady = account.stripe.hasAccount
        let browserReady = account.browserProfile.isReady
        return AccountProfile(
            displayName: account.user.displayName,
            email: account.user.email,
            memberSinceLabel: memberLabel(stripeReady: stripeReady, browserReady: browserReady),
            sections: [
                profileSection(account),
                payoutsSection(account),
                browserSection(account),
                marketplacesSection(account.marketplaces),
                aboutSection()
            ],
            stripeOnboardingURL: account.stripe.onboardingUrl,
            needsProvisionRetry: !stripeReady || !browserReady,
            statusNote: statusNote(account)
        )
    }

    private static func memberLabel(stripeReady: Bool, browserReady: Bool) -> String {
        switch (stripeReady, browserReady) {
        case (true, true):
            return "Payouts and browser are ready"
        case (false, true):
            return "Browser is ready. Payouts still need a moment"
        case (true, false):
            return "Payouts are ready. The browser still needs a moment"
        case (false, false):
            return "Payouts and browser still need a moment"
        }
    }

    private static func profileSection(_ account: SignedInAccount) -> AccountSection {
        AccountSection(
            id: "profile",
            title: "Profile",
            rows: [
                AccountRow(id: "name", title: "Name", value: account.user.displayName),
                AccountRow(id: "email", title: "Email", value: account.user.email)
            ]
        )
    }

    private static func payoutsSection(_ account: SignedInAccount) -> AccountSection {
        AccountSection(
            id: "payouts",
            title: "Payouts",
            rows: [
                AccountRow(id: "stripe", title: "Stripe", value: stripeValue(account.stripe))
            ]
        )
    }

    private static func browserSection(_ account: SignedInAccount) -> AccountSection {
        AccountSection(
            id: "browser",
            title: "Browser",
            rows: [
                AccountRow(
                    id: "browser",
                    title: "Shop browser",
                    value: account.browserProfile.isReady ? "Ready" : "Not set up"
                )
            ]
        )
    }

    private static func marketplacesSection(_ links: [MarketplaceLink]) -> AccountSection {
        var bySlug: [String: MarketplaceLink] = [:]
        for link in links where bySlug[link.marketplace] == nil {
            bySlug[link.marketplace] = link
        }
        return AccountSection(
            id: "marketplaces",
            title: "Marketplaces",
            rows: Marketplace.allCases.map { market in
                AccountRow(
                    id: market.rawValue,
                    title: market.displayName,
                    value: marketplaceValue(bySlug[market.rawValue])
                )
            },
            note: "Salt connects these shops."
        )
    }

    private static func marketplaceValue(_ link: MarketplaceLink?) -> String {
        guard let link else { return "Not connected" }
        switch link.status {
        case "connected":
            let username = link.externalUsername.trimmingCharacters(in: .whitespacesAndNewlines)
            return username.isEmpty ? "Connected" : "Connected as \(username)"
        case "needs_login":
            return "Needs login"
        case "failed":
            return "Failed"
        default:
            return "Not connected"
        }
    }

    private static func aboutSection() -> AccountSection {
        AccountSection(
            id: "about",
            title: "About",
            rows: [
                AccountRow(id: "version", title: "Version", value: "1.0")
            ]
        )
    }

    private static func stripeValue(_ stripe: StripeProvision) -> String {
        guard stripe.hasAccount else { return "Not set up" }
        switch stripe.transfersStatus {
        case "active":
            return "Ready"
        case "pending":
            return "Finish setup"
        default:
            let status = stripe.transfersStatus?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return status.isEmpty ? "Pending" : status
        }
    }

    private static func statusNote(_ account: SignedInAccount) -> String? {
        let notes = [account.stripe.error, account.browserProfile.error].compactMap { note -> String? in
            let trimmed = note?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
            return trimmed.isEmpty ? nil : trimmed
        }
        guard !notes.isEmpty else { return nil }
        return notes.joined(separator: " ")
    }
}
