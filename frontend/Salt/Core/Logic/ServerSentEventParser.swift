import Foundation

/// Splits `text/event-stream` frames from Salt's chat endpoint.
/// A frame that has not ended in a blank line stays buffered.
struct ServerSentEventParser {
    private var buffer = Data()

    mutating func append(_ chunk: Data) -> [ChatStreamEvent] {
        buffer.append(chunk)
        var events: [ChatStreamEvent] = []
        while let separator = nextSeparator() {
            let frame = buffer.subdata(in: buffer.startIndex..<separator.lowerBound)
            buffer.removeSubrange(buffer.startIndex..<separator.upperBound)
            if let event = ChatStreamEvent(serverSentFrame: frame) {
                events.append(event)
            }
        }
        return events
    }

    private func nextSeparator() -> Range<Data.Index>? {
        let lineFeed = buffer.range(of: Data([0x0A, 0x0A]))
        let carriageReturn = buffer.range(of: Data([0x0D, 0x0A, 0x0D, 0x0A]))
        switch (lineFeed, carriageReturn) {
        case (let line?, let carriage?):
            return line.lowerBound <= carriage.lowerBound ? line : carriage
        case (let line?, nil):
            return line
        case (nil, let carriage?):
            return carriage
        case (nil, nil):
            return nil
        }
    }
}

extension ChatStreamEvent {
    init?(serverSentFrame frame: Data) {
        guard let text = String(data: frame, encoding: .utf8) else { return nil }

        var name: String?
        var dataLines: [String] = []
        for rawLine in text.split(separator: "\n", omittingEmptySubsequences: false) {
            var line = Substring(rawLine)
            if line.last == "\r" {
                line = line.dropLast()
            }
            if line.hasPrefix(":") || line.isEmpty {
                continue
            }
            if line.hasPrefix("event:") {
                name = line.dropFirst("event:".count).trimmingCharacters(in: .whitespaces)
            } else if line.hasPrefix("data:") {
                var value = line.dropFirst("data:".count)
                if value.first == " " {
                    value = value.dropFirst()
                }
                dataLines.append(String(value))
            }
        }

        guard let name, !dataLines.isEmpty else { return nil }
        let payload = Data(dataLines.joined(separator: "\n").utf8)
        guard let json = try? JSONSerialization.jsonObject(with: payload) as? [String: Any] else {
            return nil
        }

        switch name {
        case "thinking":
            guard let delta = json["delta"] as? String else { return nil }
            self = .thinking(delta)
        case "message":
            guard let delta = json["delta"] as? String else { return nil }
            self = .message(delta)
        case "done":
            guard let thinking = json["thinking"] as? String, let message = json["message"] as? String else {
                return nil
            }
            self = .done(thinking: thinking, message: message)
        case "error":
            guard let message = json["error"] as? String else { return nil }
            self = .error(message)
        default:
            return nil
        }
    }
}
