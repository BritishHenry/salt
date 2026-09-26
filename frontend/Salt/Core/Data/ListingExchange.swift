import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

enum ListingExchange {
    static func listItems(
        transport: any HTTPTransport,
        baseURL: URL,
        token: String
    ) throws -> [WardrobeItem] {
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/listings/items",
            method: "GET",
            token: token,
            contentType: nil,
            body: nil
        )
        let response = try transport.send(request)
        try throwIfNeeded(response)
        return try decodeItems(response)
    }

    static func saveItem(
        transport: any HTTPTransport,
        baseURL: URL,
        token: String,
        id: String?,
        write: WardrobeItemWrite
    ) throws -> WardrobeItem {
        let path = id.map { "api/listings/items/\($0)" } ?? "api/listings/items"
        let request = try makeRequest(
            baseURL: baseURL,
            path: path,
            method: id == nil ? "POST" : "PATCH",
            token: token,
            contentType: "application/json",
            body: try write.jsonData()
        )
        let response = try transport.send(request)
        try throwIfNeeded(response)
        return try decodeItem(response)
    }

    static func uploadPhoto(
        transport: any HTTPTransport,
        baseURL: URL,
        token: String,
        itemID: String,
        filename: String,
        data: Data,
        mimeType: String
    ) throws {
        let multipart = multipartBody(filename: filename, data: data, mimeType: mimeType)
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/listings/items/\(itemID)/photos",
            method: "POST",
            token: token,
            contentType: multipart.contentType,
            body: multipart.body
        )
        let response = try transport.send(request)
        try throwIfNeeded(response)
    }

    static func deletePhoto(
        transport: any HTTPTransport,
        baseURL: URL,
        token: String,
        itemID: String,
        position: Int
    ) throws {
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/listings/items/\(itemID)/photos/\(position)",
            method: "DELETE",
            token: token,
            contentType: nil,
            body: nil
        )
        let response = try transport.send(request)
        try throwIfNeeded(response)
    }

    static func createListing(
        transport: any HTTPTransport,
        baseURL: URL,
        token: String,
        itemID: String,
        marketplace: Marketplace,
        priceMinor: Int?,
        currency: String
    ) throws {
        var object: [String: Any] = [
            "marketplace": marketplace.rawValue,
            "currency": currency
        ]
        if let priceMinor {
            object["price_minor"] = priceMinor
        }
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/listings/items/\(itemID)/listings",
            method: "POST",
            token: token,
            contentType: "application/json",
            body: try JSONSerialization.data(withJSONObject: object)
        )
        let response = try transport.send(request)
        try throwIfNeeded(response)
    }

    static func updateListing(
        transport: any HTTPTransport,
        baseURL: URL,
        token: String,
        itemID: String,
        marketplace: Marketplace,
        status: String
    ) throws {
        let body = try JSONSerialization.data(withJSONObject: ["status": status])
        let request = try makeRequest(
            baseURL: baseURL,
            path: "api/listings/items/\(itemID)/listings/\(marketplace.rawValue)",
            method: "PATCH",
            token: token,
            contentType: "application/json",
            body: body
        )
        let response = try transport.send(request)
        try throwIfNeeded(response)
    }

    static func multipartBody(filename: String, data: Data, mimeType: String) -> (body: Data, contentType: String) {
        let boundary = "SaltBoundary\(UUID().uuidString.replacingOccurrences(of: "-", with: ""))"
        var body = Data()
        func append(_ text: String) {
            body.append(Data(text.utf8))
        }
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"image\"; filename=\"\(filename)\"\r\n")
        append("Content-Type: \(mimeType)\r\n\r\n")
        body.append(data)
        append("\r\n--\(boundary)--\r\n")
        return (body, "multipart/form-data; boundary=\(boundary)")
    }

    private static func decodeItems(_ response: HTTPResponse) throws -> [WardrobeItem] {
        let envelope: ItemsEnvelope
        do {
            envelope = try JSONDecoder().decode(ItemsEnvelope.self, from: response.data)
        } catch {
            throw AccountAPIError(message: "Salt sent a response I couldn't read.", statusCode: response.statusCode)
        }
        return envelope.items.map(WardrobeItem.init(payload:))
    }

    private static func decodeItem(_ response: HTTPResponse) throws -> WardrobeItem {
        do {
            let payload = try JSONDecoder().decode(ItemPayload.self, from: response.data)
            return WardrobeItem(payload: payload)
        } catch {
            throw AccountAPIError(message: "Salt sent a response I couldn't read.", statusCode: response.statusCode)
        }
    }

    private static func throwIfNeeded(_ response: HTTPResponse) throws {
        guard (200...299).contains(response.statusCode) else {
            throw AccountExchange.serverError(response)
        }
    }

    private static func makeRequest(
        baseURL: URL,
        path: String,
        method: String,
        token: String,
        contentType: String?,
        body: Data?
    ) throws -> URLRequest {
        var request = URLRequest(url: try AccountExchange.url(baseURL: baseURL, path: path))
        request.httpMethod = method
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        if let contentType {
            request.setValue(contentType, forHTTPHeaderField: "Content-Type")
        }
        request.httpBody = body
        return request
    }
}

private struct ItemsEnvelope: Decodable {
    var items: [ItemPayload]
}

private struct ItemPayload: Decodable {
    var id: Int
    var title: String
    var brand: String
    var sizeLabel: String
    var condition: String
    var category: String
    var priceMinor: Int?
    var currency: String
    var photos: [PhotoPayload]
    var listings: [ListingPayload]

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case brand
        case condition
        case category
        case currency
        case photos
        case listings
        case sizeLabel = "size_label"
        case priceMinor = "price_minor"
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        id = try container.decode(Int.self, forKey: .id)
        title = try container.decodeIfPresent(String.self, forKey: .title) ?? ""
        brand = try container.decodeIfPresent(String.self, forKey: .brand) ?? ""
        sizeLabel = try container.decodeIfPresent(String.self, forKey: .sizeLabel) ?? ""
        condition = try container.decodeIfPresent(String.self, forKey: .condition) ?? ""
        category = try container.decodeIfPresent(String.self, forKey: .category) ?? ""
        priceMinor = try container.decodeIfPresent(Int.self, forKey: .priceMinor)
        currency = try container.decodeIfPresent(String.self, forKey: .currency) ?? "gbp"
        photos = try container.decodeIfPresent([PhotoPayload].self, forKey: .photos) ?? []
        listings = try container.decodeIfPresent([ListingPayload].self, forKey: .listings) ?? []
    }
}

private struct PhotoPayload: Decodable {
    var position: Int
    var url: String?
}

private struct ListingPayload: Decodable {
    var marketplace: String
    var status: String

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        marketplace = try container.decodeIfPresent(String.self, forKey: .marketplace) ?? ""
        status = try container.decodeIfPresent(String.self, forKey: .status) ?? ""
    }

    enum CodingKeys: String, CodingKey {
        case marketplace
        case status
    }
}

extension WardrobeItem {
    fileprivate init(payload: ItemPayload) {
        let photos = payload.photos.compactMap { photo -> WardrobePhoto? in
            let url = photo.url.flatMap { URL(string: $0) }
            return WardrobePhoto(position: photo.position, url: url)
        }
        let listings = payload.listings.compactMap { listing -> WardrobeListing? in
            guard let marketplace = Marketplace(rawValue: listing.marketplace) else { return nil }
            return WardrobeListing(marketplace: marketplace, status: listing.status)
        }
        self.init(
            id: String(payload.id),
            title: payload.title,
            brand: payload.brand,
            size: payload.sizeLabel,
            condition: payload.condition,
            pricePence: payload.priceMinor,
            currency: payload.currency,
            kind: GarmentKind.resolve(category: payload.category),
            category: payload.category,
            listings: listings,
            photos: photos.sorted { $0.position < $1.position }
        )
    }
}
