import SwiftUI

struct ChatTurnView: View {
    let turn: ChatTurn
    let agentName: String

    var body: some View {
        switch turn {
        case .user(let message):
            ChatBubble(
                text: message.text,
                isFromUser: true,
                authorName: message.authorName,
                sentAt: message.sentAt
            )
        case .agent(let agent):
            agentColumn(agent)
        }
    }

    @ViewBuilder
    private func agentColumn(_ agent: AgentTurn) -> some View {
        if agent.phase == .thinking && agent.thinking.isEmpty {
            TypingIndicator()
        } else {
            HStack(alignment: .bottom, spacing: 8) {
                SaltMark(size: 28)
                VStack(alignment: .leading, spacing: 8) {
                    thinking(for: agent)
                    if !agent.message.isEmpty {
                        hugging {
                            ChatBubble(
                                text: agent.message,
                                isFromUser: false,
                                authorName: agentName,
                                sentAt: agent.startedAt,
                                showsMark: false
                            )
                        }
                    }
                    if agent.phase == .failed, let error = agent.error, !error.isEmpty {
                        hugging {
                            Text(error)
                                .font(SaltFont.body)
                                .foregroundStyle(SaltColor.ink)
                                .multilineTextAlignment(.leading)
                                .fixedSize(horizontal: false, vertical: true)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 10)
                                .background(
                                    SaltColor.peach.opacity(0.55),
                                    in: RoundedRectangle(cornerRadius: 18, style: .continuous)
                                )
                                .accessibilityLabel("\(agentName) reported a problem. \(error)")
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    @ViewBuilder
    private func thinking(for agent: AgentTurn) -> some View {
        if agent.phase == .thinking && !agent.thinking.isEmpty {
            hugging {
                Text(agent.thinking)
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.ink)
                    .multilineTextAlignment(.leading)
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
                    .textSelection(.enabled)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(SaltColor.primarySoft, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 18, style: .continuous)
                            .stroke(SaltColor.hairline, lineWidth: 1)
                    )
                    .accessibilityElement(children: .ignore)
                    .accessibilityLabel("\(agentName) is thinking")
            }
        } else if !agent.thinking.isEmpty {
            DisclosureGroup {
                Text(agent.thinking)
                    .font(SaltFont.body)
                    .foregroundStyle(SaltColor.ink)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
            } label: {
                Text("Show thinking")
                    .font(SaltFont.caption)
                    .foregroundStyle(SaltColor.inkMuted)
            }
            .tint(SaltColor.cocoa)
            .padding(.trailing, 40)
        }
    }

    private func hugging<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        HStack(alignment: .bottom, spacing: 0) {
            content()
            Spacer(minLength: 40)
        }
    }
}
