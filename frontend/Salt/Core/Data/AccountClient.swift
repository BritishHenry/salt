import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

struct HTTPResponse: Equatable, Sendable {
    var statusCode: Int
    var data: Data
}

protocol HTTPTransport: Sendable {
    func send(_ request: URLRequest) throws -> HTTPResponse
}

protocol AccountClient: Sendable {
    func signUp(displayName: String, email: String, password: String) throws -> SignedInAccount
    func logIn(email: String, password: String) throws -> SignedInAccount
    func logOut(token: String) throws
    func currentAccount(token: String) throws -> SignedInAccount
    func provision(token: String) throws -> SignedInAccount
}

struct AccountAPIError: Error, Equatable, Sendable, LocalizedError {
    var message: String
    var statusCode: Int?

    var errorDescription: String? { message }
}

enum SaltAPIConfiguration {
    static let defaultBaseURL = URL(string: "http://127.0.0.1:8000")!

    static func baseURL(infoValue: String?) -> URL {
        let trimmed = infoValue?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        guard !trimmed.isEmpty, let url = URL(string: trimmed), url.scheme != nil, url.host != nil else {
            return defaultBaseURL
        }
        return url
    }
}

struct HTTPAccountClient: AccountClient, Sendable {
    var baseURL: URL
    var transport: any HTTPTransport

    func signUp(displayName: String, email: String, password: String) throws -> SignedInAccount {
        try AccountExchange.signUp(
            transport: transport,
            baseURL: baseURL,
            displayName: displayName,
            email: email,
            password: password
        )
    }

    func logIn(email: String, password: String) throws -> SignedInAccount {
        try AccountExchange.logIn(transport: transport, baseURL: baseURL, email: email, password: password)
    }

    func logOut(token: String) throws {
        try AccountExchange.logOut(transport: transport, baseURL: baseURL, token: token)
    }

    func currentAccount(token: String) throws -> SignedInAccount {
        try AccountExchange.currentAccount(transport: transport, baseURL: baseURL, token: token)
    }

    func provision(token: String) throws -> SignedInAccount {
        try AccountExchange.provision(transport: transport, baseURL: baseURL, token: token)
    }
}

enum AccountExchange {
    static func signUp(
        transport: any HTTPTransport,
        baseURL: URL,
        displayName: String,
        email: String,
        password: String
    ) throws -> SignedInAccount {
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/accounts/signup/",
            method: "POST",
            token: nil,
            body: try encode(
                SignupBody(
                    email: SignupForm.normalizedEmail(email),
                    password: password,
                    displayName: SignupForm.normalizedName(displayName)
                )
            )
        )
        return try decodeSignedIn(transport.send(request), keepingToken: nil)
    }

    static func logIn(
        transport: any HTTPTransport,
        baseURL: URL,
        email: String,
        password: String
    ) throws -> SignedInAccount {
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/accounts/login/",
            method: "POST",
            token: nil,
            body: try encode(LoginBody(email: SignupForm.normalizedEmail(email), password: password))
        )
        return try decodeSignedIn(transport.send(request), keepingToken: nil)
    }

    static func logOut(transport: any HTTPTransport, baseURL: URL, token: String) throws {
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/accounts/logout/",
            method: "POST",
            token: token,
            body: nil
        )
        let response = try transport.send(request)
        guard (200...299).contains(response.statusCode) else {
            throw serverError(response)
        }
    }

    static func currentAccount(transport: any HTTPTransport, baseURL: URL, token: String) throws -> SignedInAccount {
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/accounts/me/",
            method: "GET",
            token: token,
            body: nil
        )
        return try decodeSignedIn(transport.send(request), keepingToken: token)
    }

    static func provision(transport: any HTTPTransport, baseURL: URL, token: String) throws -> SignedInAccount {
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/accounts/provision/",
            method: "POST",
            token: token,
            body: nil
        )
        return try decodeSignedIn(transport.send(request), keepingToken: token)
    }

    static func decodeSignedIn(_ response: HTTPResponse, keepingToken: String?) throws -> SignedInAccount {
        guard (200...299).contains(response.statusCode) else {
            throw serverError(response)
        }
        let payload: AccountPayload
        do {
            payload = try JSONDecoder().decode(AccountPayload.self, from: response.data)
        } catch {
            throw AccountAPIError(message: "Salt sent a response I couldn't read.", statusCode: response.statusCode)
        }
        let token = payload.token ?? keepingToken
        guard let token, !token.isEmpty else {
            throw AccountAPIError(message: "Salt didn't send a login token.", statusCode: response.statusCode)
        }
        return SignedInAccount(
            token: token,
            user: payload.user,
            stripe: payload.stripe,
            browserProfile: payload.browserProfile
        )
    }

    private static func serverError(_ response: HTTPResponse) -> AccountAPIError {
        if let payload = try? JSONDecoder().decode(APIErrorBody.self, from: response.data) {
            let message = payload.error.trimmingCharacters(in: .whitespacesAndNewlines)
            if !message.isEmpty {
                return AccountAPIError(message: message, statusCode: response.statusCode)
            }
        }
        return AccountAPIError(message: "Salt couldn't finish that. Try again.", statusCode: response.statusCode)
    }

    private static func encode<Body: Encodable>(_ body: Body) throws -> Data {
        try JSONEncoder().encode(body)
    }

    private static func makeRequest(
        baseURL: URL,
        path: String,
        method: String,
        token: String?,
        body: Data?
    ) throws -> URLRequest {
        var request = URLRequest(url: try url(baseURL: baseURL, path: path))
        request.httpMethod = method
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if let token, !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let body {
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.httpBody = body
        }
        return request
    }

    static func url(baseURL: URL, path: String) throws -> URL {
        let root = baseURL.absoluteString.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let tail = path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard let url = URL(string: root + "/" + tail + "/") else {
            throw AccountAPIError(message: "Salt's server address is invalid.")
        }
        return url
    }
}

private struct AccountPayload: Decodable {
    var token: String?
    var user: AccountUser
    var stripe: StripeProvision
    var browserProfile: BrowserProvision

    enum CodingKeys: String, CodingKey {
        case token
        case user
        case stripe
        case browserProfile = "browser_profile"
    }
}

private struct APIErrorBody: Decodable {
    var error: String
}

private struct SignupBody: Encodable {
    var email: String
    var password: String
    var displayName: String

    enum CodingKeys: String, CodingKey {
        case email
        case password
        case displayName = "display_name"
    }
}

private struct LoginBody: Encodable {
    var email: String
    var password: String
}
