import SwiftUI

struct SuggestionRow: View {
    let prompts: [String]
    var onSelect: (String) -> Void

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(prompts, id: \.self) { prompt in
                    SaltChip(title: prompt) {
                        onSelect(prompt)
                    }
                }
            }
            .padding(.horizontal, 16)
        }
        .accessibilityIdentifier("chat.suggestions")
    }
}
