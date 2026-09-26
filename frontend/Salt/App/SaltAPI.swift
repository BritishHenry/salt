import Foundation

enum SaltAPI {
    static var baseURL: URL {
        let raw = Bundle.main.object(forInfoDictionaryKey: "SaltAPIBaseURL") as? String
        return SaltAPIConfiguration.baseURL(infoValue: raw)
    }
}
