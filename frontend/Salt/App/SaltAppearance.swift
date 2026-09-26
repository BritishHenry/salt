import UIKit

enum SaltAppearance {
    static func apply() {
        let tab = UITabBarAppearance()
        tab.configureWithOpaqueBackground()
        tab.backgroundColor = SaltColor.whiteUI
        tab.shadowColor = SaltColor.cocoaUI.withAlphaComponent(0.12)

        let item = UITabBarItemAppearance()
        let normalColor = SaltColor.cocoaUI.withAlphaComponent(0.72)
        let selectedColor = SaltColor.cocoaUI
        let normalFont = roundedFont(size: 10, weight: .medium)
        let selectedFont = roundedFont(size: 10, weight: .semibold)

        item.normal.iconColor = normalColor
        item.normal.titleTextAttributes = [
            .foregroundColor: normalColor,
            .font: normalFont
        ]
        item.selected.iconColor = selectedColor
        item.selected.titleTextAttributes = [
            .foregroundColor: selectedColor,
            .font: selectedFont
        ]
        tab.stackedLayoutAppearance = item
        tab.inlineLayoutAppearance = item
        tab.compactInlineLayoutAppearance = item

        let bar = UITabBar.appearance()
        bar.standardAppearance = tab
        bar.scrollEdgeAppearance = tab
        bar.tintColor = selectedColor
        bar.unselectedItemTintColor = normalColor

        let navigation = UINavigationBarAppearance()
        navigation.configureWithOpaqueBackground()
        navigation.backgroundColor = SaltColor.peachUI
        navigation.shadowColor = .clear
        navigation.titleTextAttributes = [.foregroundColor: selectedColor]
        let navigationBar = UINavigationBar.appearance()
        navigationBar.standardAppearance = navigation
        navigationBar.scrollEdgeAppearance = navigation
        navigationBar.compactAppearance = navigation
    }

    private static func roundedFont(size: CGFloat, weight: UIFont.Weight) -> UIFont {
        let base = UIFont.systemFont(ofSize: size, weight: weight)
        guard let descriptor = base.fontDescriptor.withDesign(.rounded) else { return base }
        return UIFont(descriptor: descriptor, size: size)
    }
}

enum SaltHaptic {
    static func tap() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
}
