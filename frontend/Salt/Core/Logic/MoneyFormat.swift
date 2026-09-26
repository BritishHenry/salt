enum MoneyFormat {
    static func gbp(pence: Int) -> String {
        let sign = pence < 0 ? "-" : ""
        let absolute = abs(pence)
        let pounds = grouped(absolute / 100)
        let remainder = absolute % 100
        if remainder == 0 {
            return "\(sign)£\(pounds)"
        }
        let remainderText = remainder < 10 ? "0\(remainder)" : "\(remainder)"
        return "\(sign)£\(pounds).\(remainderText)"
    }

    private static func grouped(_ value: Int) -> String {
        let digits = String(value)
        var characters: [Character] = []
        for (offset, character) in digits.reversed().enumerated() {
            if offset > 0, offset % 3 == 0 {
                characters.append(",")
            }
            characters.append(character)
        }
        return String(characters.reversed())
    }
}
