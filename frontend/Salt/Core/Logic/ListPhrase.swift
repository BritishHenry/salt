enum ListPhrase {
    static func join(_ parts: [String]) -> String {
        switch parts.count {
        case 0:
            return ""
        case 1:
            return parts[0]
        case 2:
            return "\(parts[0]) and \(parts[1])"
        default:
            let head = parts.dropLast().joined(separator: ", ")
            return "\(head), and \(parts[parts.count - 1])"
        }
    }
}
