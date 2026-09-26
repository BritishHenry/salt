import Foundation

enum AccountProfileBuilder {
    static func profile(for account: SignedInAccount) -> AccountProfile {
        let stripeReady = account.stripe.hasAccount
        let browserReady = account.browserProfile.isReady
        let money = stripeMoney(account.stripe)
        return AccountProfile(
            displayName: account.user.displayName,
            email: account.user.email,
            memberSinceLabel: memberLabel(stripeReady: stripeReady, browserReady: browserReady),
            sections: [
                profileSection(account),
                payoutsSection(account, money: money),
                browserSection(account),
                marketplacesSection(),
                aboutSection()
            ],
            stripeOnboardingURL: account.stripe.onboardingUrl,
            needsProvisionRetry: !stripeReady || !browserReady,
            statusNote: statusNote(account),
            stripeAvailableLabel: money.available,
            stripePendingLabel: money.pendingCaption
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

    private static func payoutsSection(_ account: SignedInAccount, money: StripeMoneyLabels) -> AccountSection {
        var rows = [
            AccountRow(id: "stripe", title: "Stripe", value: stripeValue(account.stripe))
        ]
        if account.stripe.balance != nil {
            if let available = money.available {
                rows.append(AccountRow(id: "balance", title: "Available", value: available))
            }
            if let pending = money.pendingAmount {
                rows.append(AccountRow(id: "pending", title: "Pending", value: pending))
            }
        }
        return AccountSection(id: "payouts", title: "Payouts", rows: rows)
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

    private static func marketplacesSection() -> AccountSection {
        AccountSection(
            id: "marketplaces",
            title: "Marketplaces",
            rows: Marketplace.allCases.map { market in
                AccountRow(id: market.rawValue, title: market.displayName, value: "Not connected")
            }
        )
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

    private struct StripeMoneyLabels {
        var available: String?
        var pendingAmount: String?
        var pendingCaption: String?
    }

    private static func stripeMoney(_ stripe: StripeProvision) -> StripeMoneyLabels {
        guard stripe.hasAccount else {
            return StripeMoneyLabels(available: "Not set up", pendingAmount: nil, pendingCaption: nil)
        }
        guard let balance = stripe.balance else {
            return StripeMoneyLabels(available: "Unavailable", pendingAmount: nil, pendingCaption: nil)
        }
        let available = moneyLabel(balance.available)
        let pendingRows = balance.pending.filter { $0.amount != 0 }
        let pendingAmount = pendingRows.isEmpty ? nil : moneyLabel(pendingRows)
        return StripeMoneyLabels(
            available: available,
            pendingAmount: pendingAmount,
            pendingCaption: pendingAmount.map { "\($0) pending" }
        )
    }

    private static func moneyLabel(_ rows: [StripeAmount]) -> String {
        if rows.isEmpty {
            return MoneyFormat.gbp(pence: 0)
        }
        return rows.map(amountLabel).joined(separator: " · ")
    }

    private static func amountLabel(_ amount: StripeAmount) -> String {
        if amount.currency.lowercased() == "gbp" {
            return MoneyFormat.gbp(pence: amount.amount)
        }
        let sign = amount.amount < 0 ? "-" : ""
        let absolute = abs(amount.amount)
        let major = absolute / 100
        let remainder = absolute % 100
        let code = amount.currency.uppercased()
        if remainder == 0 {
            return "\(sign)\(major) \(code)"
        }
        let remainderText = remainder < 10 ? "0\(remainder)" : "\(remainder)"
        return "\(sign)\(major).\(remainderText) \(code)"
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
