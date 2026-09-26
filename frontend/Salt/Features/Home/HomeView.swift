import SwiftUI

struct HomeView: View {
    @StateObject private var viewModel: HomeViewModel
    @State private var draft = ""

    init(dataSource: any ChatDataSource = MockChatDataSource()) {
        _viewModel = StateObject(wrappedValue: HomeViewModel(dataSource: dataSource))
    }

    var body: some View {
        SaltScreen {
            VStack(spacing: 0) {
                SaltChatHeader(name: viewModel.agentName)
                messages
                composer
            }
            .accessibilityIdentifier("home.chat")
        }
    }

    private var messages: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 14) {
                    ForEach(viewModel.messages) { message in
                        ChatBubble(message: message)
                            .id(message.id)
                    }
                    if viewModel.showsTypingIndicator {
                        TypingIndicator()
                            .id(Self.typingID)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .scrollDismissesKeyboard(.interactively)
            .onAppear { scrollToEnd(with: proxy, animated: false) }
            .onChange(of: viewModel.messages.count) { _ in
                scrollToEnd(with: proxy, animated: true)
            }
            .onChange(of: viewModel.messages.last?.text) { _ in
                scrollToEnd(with: proxy, animated: true)
            }
            .onChange(of: viewModel.showsTypingIndicator) { _ in
                scrollToEnd(with: proxy, animated: true)
            }
        }
    }

    private var composer: some View {
        VStack(spacing: 8) {
            if showsSuggestions {
                SuggestionRow(prompts: viewModel.suggestions) { prompt in
                    guard viewModel.send(prompt) else { return }
                    SaltHaptic.tap()
                }
            }
            ChatComposer(draft: $draft, canSend: canSend, onSend: submitDraft)
        }
        .padding(.top, 8)
        .padding(.bottom, 10)
        .background(SaltColor.background)
        .overlay(alignment: .top) {
            Rectangle()
                .fill(SaltColor.hairline)
                .frame(height: 1)
        }
    }

    private var showsSuggestions: Bool {
        draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !viewModel.isReplying
    }

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !viewModel.isReplying
    }

    private func submitDraft() {
        guard viewModel.send(draft) else { return }
        draft = ""
        SaltHaptic.tap()
    }

    private func scrollToEnd(with proxy: ScrollViewProxy, animated: Bool) {
        let target = viewModel.showsTypingIndicator ? Self.typingID : viewModel.messages.last?.id
        guard let target else { return }
        if animated {
            withAnimation(.easeOut(duration: 0.2)) {
                proxy.scrollTo(target, anchor: .bottom)
            }
        } else {
            proxy.scrollTo(target, anchor: .bottom)
        }
    }

    private static let typingID = "typing"
}

struct HomeView_Previews: PreviewProvider {
    static var previews: some View {
        HomeView()
    }
}
