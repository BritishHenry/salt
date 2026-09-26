import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

var checks = 0

func expectEqual<T: Equatable>(_ actual: T, _ expected: T, _ name: String) {
    checks += 1
    if actual != expected {
        fputs("FAIL \(name)\n  expected: \(expected)\n  actual:   \(actual)\n", stderr)
        exit(1)
    }
}

func expectTrue(_ condition: Bool, _ name: String) {
    checks += 1
    if !condition {
        fputs("FAIL \(name)\n", stderr)
        exit(1)
    }
}

func sampleItem(
    id: String = "sample",
    title: String = "Sample",
    pricePence: Int = 1000,
    listedOn: Set<Marketplace> = [.vinted],
    pendingOffer: PendingOffer? = nil
) -> WardrobeItem {
    WardrobeItem(
        id: id,
        title: title,
        brand: "Brand",
        size: "M",
        condition: "Good",
        pricePence: pricePence,
        kind: .top,
        listedOn: listedOn,
        pendingOffer: pendingOffer
    )
}

func testMoney() {
    expectEqual(MoneyFormat.gbp(pence: 2800), "£28", "whole pounds")
    expectEqual(MoneyFormat.gbp(pence: 3550), "£35.50", "pence")
    expectEqual(MoneyFormat.gbp(pence: 199), "£1.99", "pounds and pence")
    expectEqual(MoneyFormat.gbp(pence: 125000), "£1,250", "grouping")
    expectEqual(MoneyFormat.gbp(pence: 100000), "£1,000", "thousands")
    expectEqual(MoneyFormat.gbp(pence: 0), "£0", "zero")
    expectEqual(MoneyFormat.gbp(pence: -500), "-£5", "negative")
}

func testCatalog() throws {
    let items = MockWardrobe.items
    expectEqual(items.count, 8, "wardrobe count")
    expectEqual(Set(items.map(\.id)).count, items.count, "unique ids")

    let insights = WardrobeInsights(items: items)
    expectEqual(insights.count(on: .vinted), 6, "vinted count")
    expectEqual(insights.count(on: .depop), 5, "depop count")
    expectEqual(insights.count(on: .ebay), 4, "ebay count")

    for item in items {
        expectTrue(!item.title.isEmpty, "title \(item.id)")
        expectTrue(!item.brand.isEmpty, "brand \(item.id)")
        expectTrue(!item.size.isEmpty, "size \(item.id)")
        expectTrue(!item.condition.isEmpty, "condition \(item.id)")
        expectTrue(item.pricePence > 0, "price \(item.id)")
        expectTrue(!item.listedOn.isEmpty, "listed \(item.id)")
        if let offer = item.pendingOffer {
            expectTrue(offer.pence > 0 && offer.pence < item.pricePence, "offer below asking \(item.id)")
            expectTrue(item.listedOn.contains(offer.marketplace), "offer site listed \(item.id)")
        }
        let data = try JSONEncoder().encode(item)
        let decoded = try JSONDecoder().decode(WardrobeItem.self, from: data)
        expectEqual(decoded, item, "codable \(item.id)")
    }

    expectEqual(
        WardrobeFilter.marketplace(.depop).apply(to: items).map(\.id),
        ["coat", "knit", "slip", "flats", "tee"],
        "depop order"
    )
    expectEqual(
        WardrobeFilter.marketplace(.vinted).apply(to: items).map(\.id),
        ["coat", "levis", "knit", "linen", "breton", "tee"],
        "vinted order"
    )
    expectEqual(
        WardrobeFilter.marketplace(.ebay).apply(to: items).map(\.id),
        ["coat", "levis", "flats", "linen"],
        "ebay order"
    )
    expectEqual(WardrobeFilter.all.apply(to: items).count, 8, "all filter")
    expectEqual(WardrobeFilter.chips.map(\.title), ["All", "Vinted", "Depop", "eBay"], "chip titles")
    expectEqual(Marketplace.allCases.map(\.displayName), ["Vinted", "Depop", "eBay"], "market order")
}

func testInsights() {
    let items = MockWardrobe.items
    let insights = WardrobeInsights(items: items)
    expectEqual(
        insights.coverageSentence(),
        "8 pieces are listed. 6 on Vinted, 5 on Depop, and 4 on eBay.",
        "coverage"
    )
    expectEqual(
        insights.sentence(focusing: [.depop]),
        "5 pieces are on Depop, including Wool overcoat and Cream cable knit.",
        "depop sentence"
    )
    expectEqual(
        insights.sentence(focusing: [.depop, .ebay]),
        "5 on Depop and 4 on eBay.",
        "two markets"
    )
    expectEqual(
        insights.gapSentence(),
        "The easiest wins are the pieces on a single site. The Silk slip dress is only on Depop and the Striped Breton top is only on Vinted.",
        "gaps"
    )
    expectEqual(
        insights.offerSentence(),
        "There's an offer on the Levi's 501s: £35 on Vinted, against £45 asking. I won't reply to buyers on my own yet.",
        "offer"
    )
    expectEqual(
        insights.priceRangeSentence(focusing: []),
        "Asking prices run from £15 to £75.",
        "price range"
    )

    expectEqual(itemDescription(items, id: "coat"), "Listed on Vinted, Depop, and eBay.", "coat listing")
    expectEqual(itemDescription(items, id: "slip"), "Listed on Depop. Not listed on Vinted and eBay.", "slip listing")
    expectEqual(itemDescription(items, id: "levis"), "Listed on Vinted and eBay. Not listed on Depop.", "levis listing")

    let covered = items.filter { $0.listedOn.count >= 2 }
    expectEqual(
        WardrobeInsights(items: covered).gapSentence(),
        "Every piece is already on at least two sites.",
        "no gaps"
    )
    expectEqual(
        WardrobeInsights(items: [sampleItem(title: "Red coat", listedOn: [.ebay])]).gapSentence(),
        "The easiest win is the Red coat, which is only on eBay.",
        "one gap"
    )
    expectEqual(
        WardrobeInsights(items: [sampleItem(listedOn: [.vinted])]).sentence(focusing: [.ebay]),
        "Nothing is on eBay yet.",
        "empty market"
    )
    expectEqual(
        WardrobeInsights(items: [sampleItem(listedOn: [.vinted])]).sentence(focusing: [.vinted]),
        "1 piece is on Vinted, including Sample.",
        "one piece"
    )
    expectEqual(
        WardrobeInsights(items: []).priceRangeSentence(focusing: []),
        "There are no asking prices to show.",
        "no prices"
    )
    expectEqual(
        WardrobeInsights(items: [sampleItem(pricePence: 1000), sampleItem(id: "b", pricePence: 1000)])
            .priceRangeSentence(focusing: []),
        "The asking price is £10.",
        "flat price"
    )
    expectEqual(
        WardrobeInsights(items: [sampleItem(pricePence: 1000), sampleItem(id: "b", pricePence: 2050)])
            .priceRangeSentence(focusing: []),
        "Asking prices run from £10 to £20.50.",
        "mixed price"
    )

    let twoOffers = [
        sampleItem(
            id: "a",
            title: "Red coat",
            pricePence: 5000,
            listedOn: [.vinted],
            pendingOffer: PendingOffer(pence: 4000, marketplace: .vinted)
        ),
        sampleItem(
            id: "b",
            title: "Blue jeans",
            pricePence: 3000,
            listedOn: [.depop],
            pendingOffer: PendingOffer(pence: 2000, marketplace: .depop)
        )
    ]
    expectEqual(
        WardrobeInsights(items: twoOffers).offerSentence(),
        "There are offers on the Red coat (£40 on Vinted) and the Blue jeans (£20 on Depop). I won't reply to buyers on my own yet.",
        "two offers"
    )
    expectEqual(
        WardrobeInsights(items: [sampleItem()]).offerSentence(),
        "Nothing has an offer waiting.",
        "no offer"
    )

    let manySingles = (1...4).map { index in
        sampleItem(id: "s\(index)", title: "Piece \(index)", listedOn: [.vinted])
    }
    let gap = WardrobeInsights(items: manySingles).gapSentence()
    expectTrue(gap.contains("Piece 1"), "mentions first single")
    expectTrue(gap.contains("Piece 3"), "mentions third single")
    expectTrue(!gap.contains("Piece 4"), "stops after three singles")
}

func testResponder() {
    let items = MockWardrobe.items
    let insights = WardrobeInsights(items: items)
    expectEqual(MockSaltResponder.reply(to: "   ", items: items), MockCopy.emptyReply, "blank")
    expectEqual(MockSaltResponder.reply(to: "Hello", items: items), MockCopy.greetingReply, "hello")
    expectEqual(
        MockSaltResponder.reply(to: "What's listed?", items: items),
        insights.coverageSentence(),
        "listed"
    )
    expectEqual(
        MockSaltResponder.reply(to: "hello what's listed", items: items),
        insights.coverageSentence(),
        "greeting does not hide a listing question"
    )
    expectEqual(
        MockSaltResponder.reply(to: "Any offers?", items: items),
        insights.offerSentence(),
        "offers"
    )
    expectEqual(
        MockSaltResponder.reply(to: "ANY OFFERS?", items: items),
        insights.offerSentence(),
        "offers ignore case"
    )
    expectEqual(MockSaltResponder.reply(to: "Any buyers?", items: items), insights.offerSentence(), "buyers")
    expectEqual(MockSaltResponder.reply(to: "How's the week?", items: items), MockWeek.sentence(), "week")
    expectEqual(
        MockWeek.sentence(),
        "3 sales this week. £64 came in before fees, £8 went out in fees, and £56 was left.",
        "week copy"
    )
    expectEqual(MockWeek.netPence, 5600, "net")
    expectEqual(
        MockSaltResponder.reply(to: "Anything on Depop?", items: items),
        insights.sentence(focusing: [.depop]),
        "depop question"
    )
    expectEqual(
        MockSaltResponder.reply(to: "Depop and eBay", items: items),
        "5 on Depop and 4 on eBay.",
        "two market question"
    )
    expectEqual(
        MockSaltResponder.reply(to: "vinted depop ebay", items: items),
        insights.coverageSentence(),
        "all markets"
    )
    expectEqual(
        MockSaltResponder.reply(to: MockCopy.seedQuestion, items: items),
        insights.gapSentence(),
        "seed question"
    )
    expectEqual(
        MockSaltResponder.reply(to: "What should I cross-list?", items: items),
        insights.gapSentence(),
        "cross list prefers gaps"
    )
    expectEqual(
        MockSaltResponder.reply(to: "what price", items: items),
        "\(insights.coverageSentence()) \(insights.priceRangeSentence(focusing: []))",
        "prices"
    )
    expectEqual(MockSaltResponder.reply(to: "Tell me a joke", items: items), MockCopy.fallbackReply, "fallback")
    expectEqual(MockCopy.suggestions.count, 3, "three suggestions")
    expectEqual(
        MockSaltResponder.reply(to: MockCopy.suggestions[0], items: items),
        insights.coverageSentence(),
        "suggestion listed"
    )
    expectEqual(
        MockSaltResponder.reply(to: MockCopy.suggestions[1], items: items),
        insights.offerSentence(),
        "suggestion offers"
    )
    expectEqual(
        MockSaltResponder.reply(to: MockCopy.suggestions[2], items: items),
        MockWeek.sentence(),
        "suggestion week"
    )
}

func testTranscriptAndSources() throws {
    let now = Date(timeIntervalSince1970: 1_758_864_000)
    let messages = MockTranscript.opening(at: now)
    expectEqual(messages.map(\.id), ["welcome", "seed-user", "seed-salt"], "transcript ids")
    expectEqual(messages[0].text, MockCopy.welcome, "welcome")
    expectEqual(messages[0].authorName, "Salt", "salt name")
    expectTrue(!messages[0].isFromUser, "welcome role")
    expectEqual(messages[1].authorName, "You", "you")
    expectTrue(messages[1].isFromUser, "user role")
    expectEqual(messages[2].text, WardrobeInsights(items: MockWardrobe.items).gapSentence(), "seed answer")
    expectTrue(messages[0].sentAt < messages[1].sentAt && messages[1].sentAt < messages[2].sentAt, "time order")

    let message = ChatMessage(
        id: "m",
        author: .agent(name: "Salt"),
        text: "Hi",
        sentAt: Date(timeIntervalSince1970: 10)
    )
    let data = try JSONEncoder().encode(message)
    let decoded = try JSONDecoder().decode(ChatMessage.self, from: data)
    expectEqual(decoded, message, "message codable")

    let chat = MockChatDataSource()
    expectEqual(chat.agentName, SaltAgent.name, "agent name")
    expectEqual(chat.suggestions, MockCopy.suggestions, "source suggestions")
    let reply = chat.reply(to: "Hello", in: [], at: Date(timeIntervalSince1970: 1))
    expectEqual(reply.authorName, "Salt", "reply author")
    expectEqual(reply.text, MockCopy.greetingReply, "reply text")
    expectEqual(reply.sentAt, Date(timeIntervalSince1970: 1), "reply date")
    expectTrue(!reply.isFromUser, "reply role")

    let user = chat.makeUserMessage(text: "Hi", at: Date(timeIntervalSince1970: 2))
    expectEqual(user.text, "Hi", "user text")
    expectEqual(user.authorName, "You", "user author")
    expectTrue(user.isFromUser, "user message role")
    expectEqual(user.sentAt, Date(timeIntervalSince1970: 2), "user date")

    expectEqual(MockWardrobeDataSource().loadItems().map(\.id), MockWardrobe.items.map(\.id), "wardrobe source")

    let profile = MockAccountDataSource().loadProfile()
    expectEqual(profile.displayName, "Claire Bennett", "account name")
    expectEqual(profile.email, "claire.bennett@example.com", "account email")
    expectEqual(profile.sections.map(\.title), ["Profile", "Marketplaces", "Preferences", "About"], "sections")
    let marketplaces = profile.sections.first { $0.id == "marketplaces" }?.rows ?? []
    expectEqual(marketplaces.map(\.title), ["Vinted", "Depop", "eBay"], "account markets")
    expectTrue(marketplaces.allSatisfy { $0.value == "Connected" }, "markets connected")
    let version = profile.sections.first { $0.id == "about" }?.rows.first?.value ?? ""
    expectEqual(version, "1.0", "version")
}

final class ScriptedTransport: HTTPTransport, @unchecked Sendable {
    var requests: [URLRequest] = []
    var response: HTTPResponse

    init(response: HTTPResponse) {
        self.response = response
    }

    func send(_ request: URLRequest) throws -> HTTPResponse {
        requests.append(request)
        return response
    }
}

func signupFixture(token: String = "tok_1", includeToken: Bool = true) -> Data {
    let tokenField = includeToken ? "\"token\": \"\(token)\"," : ""
    let json = """
    {
      \(tokenField)
      "user": {"id": 7, "email": "ada@example.com", "display_name": "Ada"},
      "stripe": {
        "seller_id": 3,
        "stripe_account_id": "acct_123",
        "transfers_status": "pending",
        "onboarding_url": "https://stripe.test/onboard"
      },
      "browser_profile": {"status": "ready", "profile_id": "prof_1"}
    }
    """
    return Data(json.utf8)
}

func bodyObject(_ request: URLRequest) throws -> [String: String] {
    let data = request.httpBody ?? Data()
    let object = try JSONSerialization.jsonObject(with: data)
    return object as? [String: String] ?? [:]
}

func testSignup() throws {
    expectEqual(
        SignupForm.signupIssue(displayName: "  ", email: "ada@example.com", password: "secret") ?? "",
        "Add the name you sell under.",
        "blank name"
    )
    expectEqual(
        SignupForm.signupIssue(displayName: String(repeating: "a", count: 256), email: "ada@example.com", password: "secret") ?? "",
        "That name is too long.",
        "long name"
    )
    expectEqual(
        SignupForm.signupIssue(displayName: "Ada", email: "not-an-email", password: "secret") ?? "",
        "Enter a valid email address.",
        "bad email"
    )
    expectEqual(
        SignupForm.signupIssue(displayName: "Ada", email: "ada@example.com", password: "") ?? "",
        "Choose a password.",
        "blank password"
    )
    expectTrue(
        SignupForm.signupIssue(displayName: " Ada ", email: " Ada@Example.com ", password: "secret") == nil,
        "valid signup"
    )
    expectEqual(SignupForm.normalizedEmail(" Ada@Example.com "), "ada@example.com", "email normalized")
    expectEqual(
        SignupForm.loginIssue(email: "ada@example.com", password: "") ?? "",
        "Enter your password.",
        "login password"
    )
    expectEqual(
        SaltAPIConfiguration.baseURL(infoValue: nil).absoluteString,
        "http://127.0.0.1:8000",
        "default api"
    )
    expectEqual(
        SaltAPIConfiguration.baseURL(infoValue: "http://10.0.0.8:8000").absoluteString,
        "http://10.0.0.8:8000",
        "plist api"
    )
    expectEqual(
        try AccountExchange.url(baseURL: URL(string: "http://127.0.0.1:8000/")!, path: "api/accounts/signup/").absoluteString,
        "http://127.0.0.1:8000/api/accounts/signup/",
        "signup url"
    )

    let transport = ScriptedTransport(response: HTTPResponse(statusCode: 201, data: signupFixture()))
    let client = HTTPAccountClient(baseURL: URL(string: "http://127.0.0.1:8000")!, transport: transport)
    let account = try client.signUp(displayName: " Ada ", email: "Ada@Example.com", password: "b3tt3r-pass-phrase")
    let request = transport.requests[0]
    expectEqual(request.httpMethod ?? "", "POST", "signup method")
    expectEqual(request.url?.absoluteString, "http://127.0.0.1:8000/api/accounts/signup/", "signup path")
    expectEqual(request.value(forHTTPHeaderField: "Content-Type"), "application/json", "signup content type")
    expectTrue(request.value(forHTTPHeaderField: "Authorization") == nil, "signup has no token yet")
    let body = try bodyObject(request)
    expectEqual(body["email"] ?? "", "ada@example.com", "signup email")
    expectEqual(body["display_name"] ?? "", "Ada", "signup name")
    expectEqual(body["password"] ?? "", "b3tt3r-pass-phrase", "signup password")
    expectEqual(account.token, "tok_1", "signup token")
    expectEqual(account.user.id, 7, "signup user")
    expectEqual(account.stripe.stripeAccountId, "acct_123", "stripe account")
    expectEqual(account.stripe.onboardingUrl, "https://stripe.test/onboard", "stripe link")
    expectEqual(account.browserProfile.profileId, "prof_1", "browser profile")

    let profile = SignedInAccountDataSource(account: account).loadProfile()
    expectEqual(profile.displayName, "Ada", "signed in name")
    expectEqual(profile.email, "ada@example.com", "signed in email")
    expectEqual(profile.memberSinceLabel, "Payouts and browser are ready", "both ready")
    expectEqual(profile.stripeOnboardingURL, "https://stripe.test/onboard", "profile link")
    expectTrue(!profile.needsProvisionRetry, "no retry when both exist")
    expectTrue(profile.statusNote == nil, "no note when setup worked")
    let payouts = profile.sections.first { $0.id == "payouts" }?.rows.first
    expectEqual(payouts?.value ?? "", "Finish setup", "stripe pending")
    let browser = profile.sections.first { $0.id == "browser" }?.rows.first
    expectEqual(browser?.value ?? "", "Ready", "browser ready")
    let markets = profile.sections.first { $0.id == "marketplaces" }?.rows ?? []
    expectEqual(markets.map(\.value), ["Not connected", "Not connected", "Not connected"], "shops not signed in yet")

    let failedStripe = """
    {"token":"tok_2","user":{"id":7,"email":"ada@example.com","display_name":"Ada"},"stripe":{"status":"failed","error":"Stripe is down."},"browser_profile":{"status":"ready","profile_id":"prof_1"}}
    """
    let failed = try AccountExchange.decodeSignedIn(
        HTTPResponse(statusCode: 201, data: Data(failedStripe.utf8)),
        keepingToken: nil
    )
    let failedProfile = AccountProfileBuilder.profile(for: failed)
    expectEqual(failedProfile.memberSinceLabel, "Browser is ready. Payouts still need a moment", "stripe failed label")
    expectTrue(failedProfile.needsProvisionRetry, "retry after stripe failure")
    expectEqual(failedProfile.statusNote, "Stripe is down.", "stripe error note")
    expectEqual(
        failedProfile.sections.first { $0.id == "payouts" }?.rows.first?.value ?? "",
        "Not set up",
        "stripe missing"
    )

    let duplicate = HTTPResponse(
        statusCode: 409,
        data: Data("{\"error\":\"An account with this email already exists.\"}".utf8)
    )
    do {
        _ = try AccountExchange.decodeSignedIn(duplicate, keepingToken: nil)
        expectTrue(false, "duplicate should fail")
    } catch let error as AccountAPIError {
        expectEqual(error.message, "An account with this email already exists.", "duplicate message")
        expectEqual(error.statusCode ?? 0, 409, "duplicate status")
    }

    let provisionTransport = ScriptedTransport(
        response: HTTPResponse(statusCode: 200, data: signupFixture(includeToken: false))
    )
    let provisioned = try HTTPAccountClient(
        baseURL: URL(string: "http://127.0.0.1:8000/")!,
        transport: provisionTransport
    ).provision(token: "tok_existing")
    let provisionRequest = provisionTransport.requests[0]
    expectEqual(provisionRequest.url?.absoluteString, "http://127.0.0.1:8000/api/accounts/provision/", "provision path")
    expectEqual(provisionRequest.value(forHTTPHeaderField: "Authorization"), "Bearer tok_existing", "provision auth")
    expectTrue(provisionRequest.httpBody == nil, "provision has no body")
    expectEqual(provisioned.token, "tok_existing", "provision keeps token")
    expectEqual(provisioned.stripe.stripeAccountId, "acct_123", "provision retries stripe")

    let logoutTransport = ScriptedTransport(response: HTTPResponse(statusCode: 204, data: Data()))
    try HTTPAccountClient(baseURL: SaltAPIConfiguration.defaultBaseURL, transport: logoutTransport)
        .logOut(token: "tok_1")
    expectEqual(logoutTransport.requests[0].httpMethod ?? "", "POST", "logout method")
    expectEqual(
        logoutTransport.requests[0].url?.absoluteString,
        "http://127.0.0.1:8000/api/accounts/logout/",
        "logout path"
    )

    let memory = MemorySessionStore()
    expectTrue(memory.load() == nil, "empty memory session")
    memory.save(account)
    expectEqual(memory.load(), Optional(account), "memory session round trip")
    memory.clear()
    expectTrue(memory.load() == nil, "memory session cleared")

    let suite = "salt.signup.tests"
    guard let defaults = UserDefaults(suiteName: suite) else {
        expectTrue(false, "user defaults suite")
        return
    }
    defaults.removePersistentDomain(forName: suite)
    let store = UserDefaultsSessionStore(defaults: defaults)
    expectTrue(store.load() == nil, "empty session")
    store.save(account)
    expectEqual(store.load(), Optional(account), "session round trip")
    store.clear()
    expectTrue(store.load() == nil, "session cleared")
    defaults.removePersistentDomain(forName: suite)
}

func itemDescription(_ items: [WardrobeItem], id: String) -> String {
    items.first { $0.id == id }?.listingDescription ?? ""
}

do {
    testMoney()
    try testCatalog()
    testInsights()
    testResponder()
    try testTranscriptAndSources()
    try testSignup()
} catch {
    fputs("FAIL \(error)\n", stderr)
    exit(1)
}

print("PASS \(checks) checks")
