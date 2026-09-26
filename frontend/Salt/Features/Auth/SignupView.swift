import SwiftUI
import UIKit

struct SignupView: View {
    @ObservedObject var session: SessionController
    @State private var mode: Mode = .signUp
    @State private var displayName = ""
    @State private var email = ""
    @State private var password = ""
    @State private var errorMessage: String?

    private enum Mode {
        case signUp
        case logIn
    }

    var body: some View {
        SaltScreen {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    HStack {
                        Spacer()
                        SaltMark(size: 72)
                        Spacer()
                    }
                    .accessibilityHidden(true)
                    SaltScreenHeader(title: title, subtitle: subtitle)
                    fields
                    if let errorMessage {
                        Text(errorMessage)
                            .font(SaltFont.body)
                            .foregroundStyle(SaltColor.cocoa)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(14)
                            .background(SaltColor.peach, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                            .accessibilityIdentifier("signup.error")
                    }
                    submitButton
                    switchButton
                }
                .padding(16)
                .padding(.bottom, 12)
            }
            .accessibilityIdentifier("signup.screen")
        }
    }

    private var title: String {
        mode == .signUp ? "Join Salt" : "Welcome back"
    }

    private var subtitle: String {
        mode == .signUp
            ? "Salt opens a Stripe payout account and a browser for Vinted, Depop, and eBay."
            : "Pick up the wardrobe you already started."
    }

    private var fields: some View {
        VStack(spacing: 12) {
            if mode == .signUp {
                field(
                    title: "Name",
                    text: $displayName,
                    prompt: "The name you sell under",
                    identifier: "signup.name",
                    contentType: .name,
                    capitalization: .words
                )
            }
            field(
                title: "Email",
                text: $email,
                prompt: "you@example.com",
                identifier: "signup.email",
                contentType: .emailAddress,
                keyboard: .emailAddress
            )
            secureField
        }
    }

    private var secureField: some View {
        SecureField(
            "Password",
            text: $password,
            prompt: Text("Password").foregroundColor(SaltColor.cocoa.opacity(0.72))
        )
        .font(SaltFont.body)
        .foregroundStyle(SaltColor.cocoa)
        .textContentType(mode == .signUp ? .newPassword : .password)
        .textInputAutocapitalization(.never)
        .autocorrectionDisabled()
        .submitLabel(.go)
        .onSubmit(submit)
        .padding(.horizontal, 16)
        .frame(minHeight: 52)
        .background(SaltColor.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(SaltColor.hairline, lineWidth: 1)
        )
        .accessibilityIdentifier("signup.password")
    }

    private var submitButton: some View {
        Button(action: submit) {
            ZStack {
                Text(buttonTitle)
                    .font(SaltFont.headline)
                    .opacity(session.isWorking ? 0 : 1)
                if session.isWorking {
                    ProgressView()
                        .tint(SaltColor.onPrimary)
                }
            }
            .foregroundStyle(SaltColor.onPrimary)
            .frame(maxWidth: .infinity)
            .frame(minHeight: 52)
            .background(SaltColor.primary, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .buttonStyle(.plain)
        .disabled(session.isWorking)
        .accessibilityIdentifier("signup.submit")
    }

    private var switchButton: some View {
        Button(action: toggleMode) {
            Text(mode == .signUp ? "I already have an account" : "Need an account?")
                .font(SaltFont.chip)
                .foregroundStyle(SaltColor.cocoa)
                .frame(maxWidth: .infinity)
                .frame(minHeight: 44)
        }
        .buttonStyle(.plain)
        .disabled(session.isWorking)
        .accessibilityIdentifier("signup.switch")
    }

    private var buttonTitle: String {
        if session.isWorking {
            return mode == .signUp ? "Setting up payouts and a browser" : "Logging in"
        }
        return mode == .signUp ? "Create account" : "Log in"
    }

    private func field(
        title: String,
        text: Binding<String>,
        prompt: String,
        identifier: String,
        contentType: UITextContentType,
        keyboard: UIKeyboardType = .default,
        capitalization: TextInputAutocapitalization = .never
    ) -> some View {
        TextField(
            title,
            text: text,
            prompt: Text(prompt).foregroundColor(SaltColor.cocoa.opacity(0.72))
        )
        .font(SaltFont.body)
        .foregroundStyle(SaltColor.cocoa)
        .textContentType(contentType)
        .keyboardType(keyboard)
        .textInputAutocapitalization(capitalization)
        .autocorrectionDisabled(keyboard == .emailAddress)
        .submitLabel(.next)
        .padding(.horizontal, 16)
        .frame(minHeight: 52)
        .background(SaltColor.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .stroke(SaltColor.hairline, lineWidth: 1)
        )
        .accessibilityIdentifier(identifier)
    }

    private func submit() {
        guard !session.isWorking else { return }
        errorMessage = nil
        let name = displayName
        let address = email
        let secret = password
        let currentMode = mode
        Task {
            do {
                switch currentMode {
                case .signUp:
                    try await session.signUp(displayName: name, email: address, password: secret)
                case .logIn:
                    try await session.logIn(email: address, password: secret)
                }
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }

    private func toggleMode() {
        mode = mode == .signUp ? .logIn : .signUp
        errorMessage = nil
    }
}
