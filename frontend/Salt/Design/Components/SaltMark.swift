import SwiftUI

struct SaltMark: View {
    var size: CGFloat

    var body: some View {
        ZStack {
            HStack(spacing: size * 0.16) {
                ear
                ear
            }
            .offset(y: -size * 0.28)

            Circle()
                .fill(SaltColor.lilac)
                .frame(width: size * 0.72, height: size * 0.72)
                .offset(y: size * 0.08)

            HStack(spacing: size * 0.16) {
                eye
                eye
            }
            .offset(y: size * 0.06)

            Circle()
                .fill(SaltColor.green)
                .frame(width: size * 0.1, height: size * 0.1)
                .offset(y: size * 0.18)
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }

    private var ear: some View {
        SaltEar()
            .fill(SaltColor.cocoa)
            .frame(width: size * 0.28, height: size * 0.32)
    }

    private var eye: some View {
        Circle()
            .fill(SaltColor.cocoa)
            .frame(width: max(size * 0.08, 2), height: max(size * 0.08, 2))
    }
}

private struct SaltEar: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.midX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        path.closeSubpath()
        return path
    }
}
