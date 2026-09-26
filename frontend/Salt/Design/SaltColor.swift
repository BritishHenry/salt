import SwiftUI
import UIKit

enum SaltRGB {
    static func components(_ hex: UInt32) -> (red: CGFloat, green: CGFloat, blue: CGFloat) {
        let red = CGFloat((hex >> 16) & 0xFF) / 255
        let green = CGFloat((hex >> 8) & 0xFF) / 255
        let blue = CGFloat(hex & 0xFF) / 255
        return (red, green, blue)
    }
}

extension Color {
    init(saltHex hex: UInt32) {
        let channels = SaltRGB.components(hex)
        self.init(
            .sRGB,
            red: Double(channels.red),
            green: Double(channels.green),
            blue: Double(channels.blue),
            opacity: 1
        )
    }
}

extension UIColor {
    convenience init(saltHex hex: UInt32) {
        let channels = SaltRGB.components(hex)
        self.init(red: channels.red, green: channels.green, blue: channels.blue, alpha: 1)
    }
}

/// Brand colours from the product palette. Green, peach, and lilac are fills.
/// Cocoa is the ink, so text stays readable on those fills.
enum SaltColor {
    static let green = Color(saltHex: 0x08CB00)
    static let white = Color(saltHex: 0xFFFFFF)
    static let peach = Color(saltHex: 0xFFCAB1)
    static let cocoa = Color(saltHex: 0x362C28)
    static let lilac = Color(saltHex: 0x9D75CB)

    static let background = peach
    static let surface = white
    static var hairline: Color { cocoa.opacity(0.12) }

    static let greenUI = UIColor(saltHex: 0x08CB00)
    static let whiteUI = UIColor(saltHex: 0xFFFFFF)
    static let peachUI = UIColor(saltHex: 0xFFCAB1)
    static let cocoaUI = UIColor(saltHex: 0x362C28)
}
