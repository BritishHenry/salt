import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

struct LiveWardrobeDataSource: WardrobeDataSource {
    var token: String
    var baseURL: URL
    var transport: any HTTPTransport

    func loadItems() async throws -> [WardrobeItem] {
        let transport = transport
        let baseURL = baseURL
        let token = token
        return try await Task.detached {
            try ListingExchange.listItems(transport: transport, baseURL: baseURL, token: token)
        }.value
    }

    func saveItem(_ write: WardrobeItemWrite, id: String?) async throws -> WardrobeItem {
        let transport = transport
        let baseURL = baseURL
        let token = token
        return try await Task.detached {
            try ListingExchange.saveItem(
                transport: transport,
                baseURL: baseURL,
                token: token,
                id: id,
                write: write
            )
        }.value
    }

    func uploadPhoto(itemID: String, filename: String, data: Data, mimeType: String) async throws {
        let transport = transport
        let baseURL = baseURL
        let token = token
        try await Task.detached {
            try ListingExchange.uploadPhoto(
                transport: transport,
                baseURL: baseURL,
                token: token,
                itemID: itemID,
                filename: filename,
                data: data,
                mimeType: mimeType
            )
        }.value
    }

    func deletePhoto(itemID: String, position: Int) async throws {
        let transport = transport
        let baseURL = baseURL
        let token = token
        try await Task.detached {
            try ListingExchange.deletePhoto(
                transport: transport,
                baseURL: baseURL,
                token: token,
                itemID: itemID,
                position: position
            )
        }.value
    }

    func createListing(
        itemID: String,
        marketplace: Marketplace,
        priceMinor: Int?,
        currency: String
    ) async throws {
        let transport = transport
        let baseURL = baseURL
        let token = token
        try await Task.detached {
            try ListingExchange.createListing(
                transport: transport,
                baseURL: baseURL,
                token: token,
                itemID: itemID,
                marketplace: marketplace,
                priceMinor: priceMinor,
                currency: currency
            )
        }.value
    }

    func updateListing(itemID: String, marketplace: Marketplace, status: String) async throws {
        let transport = transport
        let baseURL = baseURL
        let token = token
        try await Task.detached {
            try ListingExchange.updateListing(
                transport: transport,
                baseURL: baseURL,
                token: token,
                itemID: itemID,
                marketplace: marketplace,
                status: status
            )
        }.value
    }
}
