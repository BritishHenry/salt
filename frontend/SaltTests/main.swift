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
    let turns = MockTranscript.opening(at: now)
    expectEqual(turns.map(\.id), ["welcome", "seed-user", "seed-salt"], "transcript ids")
    expectEqual(agentMessage(turns[0]) ?? "", MockCopy.welcome, "welcome")
    expectTrue(isAgent(turns[0]), "welcome role")
    expectEqual(userMessage(turns[1])?.authorName ?? "", "You", "you")
    expectTrue(isUser(turns[1]), "user role")
    expectEqual(
        agentMessage(turns[2]) ?? "",
        WardrobeInsights(items: MockWardrobe.items).gapSentence(),
        "seed answer"
    )
    expectTrue(turns[0].sentAt < turns[1].sentAt && turns[1].sentAt < turns[2].sentAt, "time order")
    if case .agent(let welcome) = turns[0] {
        expectEqual(welcome.phase, .complete, "welcome complete")
        expectEqual(welcome.thinking, "", "welcome thinking hidden")
    } else {
        expectTrue(false, "welcome is an agent turn")
    }

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
    let events = MockSaltStream.events(for: "Hello")
    expectEqual(events.count, 4, "mock event count")
    if case .done(let thinking, let message) = events.last {
        expectEqual(thinking, "Checking the wardrobe.", "mock thinking")
        expectEqual(message, MockCopy.greetingReply, "mock done message")
    } else {
        expectTrue(false, "mock stream ends with done")
    }
    expectEqual(messageDeltas(in: events).joined(), MockCopy.greetingReply, "deltas rebuild reply")
    expectEqual(messageDeltas(in: events).count, 2, "two message deltas")

    let sentAt = Date(timeIntervalSince1970: 2)
    if case .user(let user) = chat.makeUserTurn(text: "Hi", at: sentAt) {
        expectEqual(user.text, "Hi", "user text")
        expectEqual(user.authorName, "You", "user author")
        expectTrue(user.isFromUser, "user message role")
        expectEqual(user.sentAt, sentAt, "user date")
    } else {
        expectTrue(false, "user turn")
    }

    let started = Date(timeIntervalSince1970: 3)
    let agent = chat.makeAgentTurn(at: started)
    expectEqual(agent.phase, .thinking, "agent starts thinking")
    expectEqual(agent.thinking, "", "agent thinking empty")
    expectEqual(agent.message, "", "agent message empty")
    expectTrue(agent.error == nil, "agent error empty")
    expectEqual(agent.startedAt, started, "agent date")

    expectEqual(MockWardrobeDataSource().loadItems().map(\.id), MockWardrobe.items.map(\.id), "wardrobe source")

    let profile = MockAccountDataSource().loadProfile()
    expectEqual(profile.displayName, "Claire Bennett", "account name")
    expectEqual(profile.email, "claire.bennett@example.com", "account email")
    expectEqual(profile.stripeAvailableLabel, "£128", "mock stripe money")
    expectEqual(profile.stripePendingLabel, "£24 pending", "mock pending money")
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
        "onboarding_url": "https://stripe.test/onboard",
        "balance": {
          "available": [{"amount": 1250, "currency": "gbp"}],
          "pending": [{"amount": 400, "currency": "gbp"}]
        }
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
    let payouts = profile.sections.first { $0.id == "payouts" }?.rows ?? []
    expectEqual(payouts.first?.value ?? "", "Finish setup", "stripe pending")
    expectEqual(payouts.map(\.title), ["Stripe", "Available", "Pending"], "payout rows")
    expectEqual(payouts.first { $0.id == "balance" }?.value ?? "", "£12.50", "stripe available")
    expectEqual(payouts.first { $0.id == "pending" }?.value ?? "", "£4", "stripe pending amount")
    expectEqual(profile.stripeAvailableLabel, "£12.50", "available label")
    expectEqual(profile.stripePendingLabel, "£4 pending", "pending caption")
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
    expectEqual(failedProfile.stripeAvailableLabel, "Not set up", "no stripe money")
    expectTrue(failedProfile.stripePendingLabel == nil, "no pending without stripe")

    let missingBalance = """
    {"token":"tok_3","user":{"id":7,"email":"ada@example.com","display_name":"Ada"},"stripe":{"seller_id":3,"stripe_account_id":"acct_123","transfers_status":"active"},"browser_profile":{"status":"ready","profile_id":"prof_1"}}
    """
    let missing = try AccountExchange.decodeSignedIn(
        HTTPResponse(statusCode: 200, data: Data(missingBalance.utf8)),
        keepingToken: nil
    )
    let missingProfile = AccountProfileBuilder.profile(for: missing)
    expectEqual(missingProfile.stripeAvailableLabel, "Unavailable", "balance missing")
    expectTrue(missingProfile.stripePendingLabel == nil, "no pending without a balance")

    let mixed = """
    {"token":"tok_4","user":{"id":7,"email":"ada@example.com","display_name":"Ada"},"stripe":{"seller_id":3,"stripe_account_id":"acct_123","transfers_status":"active","balance":{"available":[{"amount":1250,"currency":"gbp"},{"amount":350,"currency":"usd"}],"pending":[{"amount":0,"currency":"gbp"}]}},"browser_profile":{"status":"ready","profile_id":"prof_1"}}
    """
    let mixedAccount = try AccountExchange.decodeSignedIn(
        HTTPResponse(statusCode: 200, data: Data(mixed.utf8)),
        keepingToken: nil
    )
    let mixedProfile = AccountProfileBuilder.profile(for: mixedAccount)
    expectEqual(mixedProfile.stripeAvailableLabel, "£12.50 · 3.50 USD", "mixed currencies")
    expectTrue(mixedProfile.stripePendingLabel == nil, "zero pending hidden")

    let emptyBalance = """
    {"token":"tok_5","user":{"id":7,"email":"ada@example.com","display_name":"Ada"},"stripe":{"seller_id":3,"stripe_account_id":"acct_123","transfers_status":"active","balance":{"available":[],"pending":[]}},"browser_profile":{"status":"ready","profile_id":"prof_1"}}
    """
    let emptyAccount = try AccountExchange.decodeSignedIn(
        HTTPResponse(statusCode: 200, data: Data(emptyBalance.utf8)),
        keepingToken: nil
    )
    expectEqual(
        AccountProfileBuilder.profile(for: emptyAccount).stripeAvailableLabel,
        "£0",
        "empty balance"
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

func testAgentTurnReducer() {
    let started = Date(timeIntervalSince1970: 0)
    var turn = AgentTurn(
        id: "t",
        thinking: "",
        message: "",
        phase: .thinking,
        error: nil,
        startedAt: started
    )
    turn = AgentTurnReducer.apply(.thinking("Checking the week. "), to: turn)
    turn = AgentTurnReducer.apply(.thinking("No new sales."), to: turn)
    expectEqual(turn.thinking, "Checking the week. No new sales.", "thinking joins")
    expectEqual(turn.phase, .thinking, "still thinking")
    expectEqual(turn.message, "", "message still empty")

    turn = AgentTurnReducer.apply(.message("Nothing sold "), to: turn)
    expectEqual(turn.phase, .writing, "first message writes")
    expectEqual(turn.message, "Nothing sold ", "first message")
    turn = AgentTurnReducer.apply(.message("this week."), to: turn)
    expectEqual(turn.message, "Nothing sold this week.", "message joins")
    expectEqual(turn.phase, .writing, "stays writing")

    turn = AgentTurnReducer.apply(
        .done(thinking: "Full thinking", message: "Full reply"),
        to: turn
    )
    expectEqual(turn.thinking, "Full thinking", "done replaces thinking")
    expectEqual(turn.message, "Full reply", "done replaces message")
    expectEqual(turn.phase, .complete, "done completes")
    expectTrue(turn.error == nil, "done clears error")

    turn = AgentTurnReducer.apply(.message("nope"), to: turn)
    expectEqual(turn.message, "Full reply", "ignore after complete")
    expectEqual(turn.phase, .complete, "stays complete")

    var failed = AgentTurn(
        id: "f",
        thinking: "",
        message: "",
        phase: .thinking,
        error: nil,
        startedAt: started
    )
    failed = AgentTurnReducer.apply(.thinking("Starting."), to: failed)
    failed = AgentTurnReducer.apply(.message("Partial "), to: failed)
    failed = AgentTurnReducer.apply(.error("The Grok API could not be reached."), to: failed)
    expectEqual(failed.phase, .failed, "error fails the turn")
    expectEqual(failed.message, "Partial ", "error keeps partial reply")
    expectEqual(failed.thinking, "Starting.", "error keeps thinking")
    expectEqual(failed.error, "The Grok API could not be reached.", "error text")
    failed = AgentTurnReducer.apply(.thinking("more"), to: failed)
    expectEqual(failed.thinking, "Starting.", "ignore after failed")
    expectEqual(failed.phase, .failed, "stays failed")
}

func testServerSentEvents() {
    let wire = """
    event: thinking
    data: {"delta":"Looking at the wardrobe. "}

    event: thinking
    data: {"delta":"One coat is live."}

    event: message
    data: {"delta":"Your wool coat "}

    event: message
    data: {"delta":"is on Vinted."}

    event: done
    data: {"thinking":"Looking at the wardrobe. One coat is live.","message":"Your wool coat is on Vinted."}

    """ + "\n"
    let expected: [ChatStreamEvent] = [
        .thinking("Looking at the wardrobe. "),
        .thinking("One coat is live."),
        .message("Your wool coat "),
        .message("is on Vinted."),
        .done(
            thinking: "Looking at the wardrobe. One coat is live.",
            message: "Your wool coat is on Vinted."
        )
    ]
    var parser = ServerSentEventParser()
    expectEqual(parser.append(Data(wire.utf8)), expected, "sse frames")

    let bytes = Data(wire.utf8)
    let split = bytes.index(bytes.startIndex, offsetBy: bytes.count / 2)
    var splitParser = ServerSentEventParser()
    let first = splitParser.append(bytes.subdata(in: bytes.startIndex..<split))
    let second = splitParser.append(bytes.subdata(in: split..<bytes.endIndex))
    expectEqual(first + second, expected, "sse split mid-frame")
    expectTrue(first.count < expected.count, "split holds a partial frame")

    var partial = ServerSentEventParser()
    expectEqual(
        partial.append(Data("event: thinking\ndata: {\"delta\":\"Hi".utf8)),
        [],
        "partial frame waits"
    )
    expectEqual(
        partial.append(Data("\"}\n\n".utf8)),
        [.thinking("Hi")],
        "partial frame completes"
    )

    var quoted = ServerSentEventParser()
    expectEqual(
        quoted.append(Data("event: message\ndata: {\"delta\":\"Say \\\"hi\\\"\"}\n\n".utf8)),
        [.message("Say \"hi\"")],
        "sse json string"
    )

    var skipped = ServerSentEventParser()
    let mixed = """
    event: ping
    data: {"ok":true}

    event: error
    data: {"error":"The Grok API could not be reached."}

    """ + "\n"
    expectEqual(
        skipped.append(Data(mixed.utf8)),
        [.error("The Grok API could not be reached.")],
        "unknown event skipped"
    )
}

func isAgent(_ turn: ChatTurn) -> Bool {
    if case .agent = turn { return true }
    return false
}

func isUser(_ turn: ChatTurn) -> Bool {
    if case .user = turn { return true }
    return false
}

func agentMessage(_ turn: ChatTurn) -> String? {
    if case .agent(let agent) = turn { return agent.message }
    return nil
}

func userMessage(_ turn: ChatTurn) -> ChatMessage? {
    if case .user(let message) = turn { return message }
    return nil
}

func messageDeltas(in events: [ChatStreamEvent]) -> [String] {
    events.compactMap { event in
        if case .message(let delta) = event { return delta }
        return nil
    }
}

func testSaltChatExchange() throws {
    let welcome = ChatTurn.agent(
        AgentTurn(
            id: "local:welcome",
            thinking: "",
            message: "Hello, I'm Salt.",
            phase: .complete,
            error: nil,
            startedAt: Date(timeIntervalSince1970: 1)
        )
    )
    let asked = ChatTurn.user(
        ChatMessage(
            id: "u1",
            author: .user,
            text: "What is listed?",
            sentAt: Date(timeIntervalSince1970: 2)
        )
    )
    let answered = ChatTurn.agent(
        AgentTurn(
            id: "a1",
            thinking: "",
            message: "The coat is on Vinted.",
            phase: .complete,
            error: nil,
            startedAt: Date(timeIntervalSince1970: 3)
        )
    )
    let blank = ChatTurn.user(
        ChatMessage(id: "blank", author: .user, text: "  ", sentAt: Date())
    )
    expectEqual(
        SaltChatExchange.wireMessages(from: [welcome, asked, answered, blank]),
        [
            SaltChatWireMessage(role: "user", content: "What is listed?"),
            SaltChatWireMessage(role: "assistant", content: "The coat is on Vinted.")
        ],
        "wire messages skip the local welcome"
    )

    let request = try SaltChatExchange.request(
        baseURL: SaltAPIConfiguration.defaultBaseURL,
        token: "tok_1",
        transcript: [welcome, asked]
    )
    expectEqual(request.httpMethod ?? "", "POST", "chat method")
    expectEqual(request.url?.absoluteString, "http://127.0.0.1:8000/api/agents/salt/chat/", "chat path")
    expectEqual(request.value(forHTTPHeaderField: "Authorization"), "Bearer tok_1", "chat auth")
    expectEqual(request.value(forHTTPHeaderField: "Accept"), "text/event-stream", "chat accept")
    let body = try JSONDecoder().decode(ChatRequestFixture.self, from: request.httpBody ?? Data())
    expectEqual(body.messages, [SaltChatWireMessage(role: "user", content: "What is listed?")], "chat body")

    var parser = SaltChatSSEParser()
    let first = parser.append("event: thinking\ndata: {\"delta\":\"Looking.\"}\n")
    expectEqual(first, [], "parser waits for a blank line")
    let streamed = parser.append("\nevent: message\ndata: {\"delta\":\"Your coat \"}\n\n")
    expectEqual(
        streamed,
        [.thinking("Looking."), .message("Your coat ")],
        "parser reads complete events"
    )
    let rest = parser.append("event: message\ndata: {\"delta\":\"is on Vinted.\"}\n\nevent: done\ndata: {\"thinking\":\"Looking.\",\"message\":\"Your coat is on Vinted.\"}\n\n")
    expectEqual(
        rest,
        [
            .message("is on Vinted."),
            .done(thinking: "Looking.", message: "Your coat is on Vinted.")
        ],
        "parser reads the rest of the stream"
    )

    var split = SaltChatSSEParser()
    _ = split.append("event: error\ndata: {\"error\":\"The Grok API ")
    let failed = split.append("could not be reached.\"}\n\n")
    expectEqual(failed, [.failure("The Grok API could not be reached.")], "parser joins a split data line")

    var draft = SaltChatDraft()
    draft.apply(.thinking("Looking."))
    draft.apply(.message("Your coat "))
    draft.apply(.done(thinking: "Looking.", message: "Your coat is on Vinted."))
    expectEqual(draft.thinking, "Looking.", "done replaces thinking")
    expectEqual(draft.message, "Your coat is on Vinted.", "done replaces the reply")
    draft.apply(.failure("The Grok API could not be reached."))
    expectEqual(
        draft.message,
        "Your coat is on Vinted.\n\nThe Grok API could not be reached.",
        "failure is appended"
    )

    var empty = SaltChatDraft()
    empty.apply(.failure("  "))
    expectEqual(empty.message, "Salt couldn't finish that. Try again.", "blank failure")

    let denied = SaltChatExchange.message(
        forHTTPError: 401,
        body: Data("{\"error\":\"Authentication required.\"}".utf8)
    )
    expectEqual(denied, "Authentication required.", "http error message")
}

private struct ChatRequestFixture: Decodable {
    var messages: [SaltChatWireMessage]
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
    testAgentTurnReducer()
    testServerSentEvents()
    try testSignup()
    try testSaltChatExchange()
} catch {
    fputs("FAIL \(error)\n", stderr)
    exit(1)
}

print("PASS \(checks) checks")
