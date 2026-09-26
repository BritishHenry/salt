enum MockAccount {
    static let profile = AccountProfile(
        displayName: "Claire Bennett",
        email: "claire.bennett@example.com",
        memberSinceLabel: "Selling since March 2024",
        sections: [
            AccountSection(
                id: "profile",
                title: "Profile",
                rows: [
                    AccountRow(id: "name", title: "Name", value: "Claire Bennett"),
                    AccountRow(id: "email", title: "Email", value: "claire.bennett@example.com")
                ]
            ),
            AccountSection(
                id: "marketplaces",
                title: "Marketplaces",
                rows: [
                    AccountRow(id: Marketplace.vinted.rawValue, title: "Vinted", value: "Connected"),
                    AccountRow(id: Marketplace.depop.rawValue, title: "Depop", value: "Connected"),
                    AccountRow(id: Marketplace.ebay.rawValue, title: "eBay", value: "Connected")
                ]
            ),
            AccountSection(
                id: "preferences",
                title: "Preferences",
                rows: [
                    AccountRow(id: "currency", title: "Currency", value: "GBP"),
                    AccountRow(id: "location", title: "Location", value: "United Kingdom"),
                    AccountRow(id: "offers", title: "Offer alerts", value: "On"),
                    AccountRow(id: "summary", title: "Morning summary", value: "On")
                ]
            ),
            AccountSection(
                id: "about",
                title: "About",
                rows: [
                    AccountRow(id: "version", title: "Version", value: "1.0")
                ]
            )
        ],
        stripeAvailableLabel: "£128",
        stripePendingLabel: "£24 pending"
    )
}
