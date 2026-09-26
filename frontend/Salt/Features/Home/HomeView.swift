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
                transcript
                composer
            }
            .accessibilityIdentifier("home.chat")
        }
    }

    private var transcript: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(spacing: 14) {
                    ForEach(viewModel.turns) { turn in
                        ChatTurnView(turn: turn, agentName: viewModel.agentName)
                            .id(turn.id)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 12)
            }
            .scrollDismissesKeyboard(.interactively)
            .onAppear { scrollToEnd(with: proxy, animated: false) }
            .onChange(of: viewModel.scrollRevision) { _ in
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
        guard let target = viewModel.turns.last?.id else { return }
        if animated {
            withAnimation(.easeOut(duration: 0.2)) {
                proxy.scrollTo(target, anchor: .bottom)
            }
        } else {
            proxy.scrollTo(target, anchor: .bottom)
        }
    }
}

struct HomeView_Previews: PreviewProvider {
    static var previews: some View {
        HomeView()
    }
}
