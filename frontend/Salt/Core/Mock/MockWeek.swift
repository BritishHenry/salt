enum MockWeek {
    static let salesCount = 3
    static let grossPence = 6400
    static let feesPence = 800

    static var netPence: Int { grossPence - feesPence }

    static func sentence() -> String {
        let label = salesCount == 1 ? "sale" : "sales"
        let gross = MoneyFormat.gbp(pence: grossPence)
        let fees = MoneyFormat.gbp(pence: feesPence)
        let net = MoneyFormat.gbp(pence: netPence)
        return "\(salesCount) \(label) this week. \(gross) came in before fees, \(fees) went out in fees, and \(net) was left."
    }
}
