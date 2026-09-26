import SwiftUI

struct WrappingHStack: Layout {
    var horizontalSpacing: CGFloat = 6
    var verticalSpacing: CGFloat = 6

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let maxWidth = proposal.width ?? .greatestFiniteMagnitude
        let rows = makeRows(subviews: subviews, maxWidth: maxWidth)
        let height = rows.reduce(CGFloat(0)) { $0 + $1.height }
            + verticalSpacing * CGFloat(max(rows.count - 1, 0))
        let contentWidth = rows.map(\.width).max() ?? 0
        return CGSize(width: proposal.width ?? contentWidth, height: height)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = makeRows(subviews: subviews, maxWidth: bounds.width)
        var y = bounds.minY
        for row in rows {
            var x = bounds.minX
            for element in row.elements {
                element.subview.place(
                    at: CGPoint(x: x, y: y),
                    anchor: .topLeading,
                    proposal: ProposedViewSize(width: element.size.width, height: element.size.height)
                )
                x += element.size.width + horizontalSpacing
            }
            y += row.height + verticalSpacing
        }
    }

    private struct Element {
        let subview: LayoutSubview
        let size: CGSize
    }

    private struct Row {
        var elements: [Element] = []
        var width: CGFloat = 0
        var height: CGFloat = 0
    }

    private func makeRows(subviews: Subviews, maxWidth: CGFloat) -> [Row] {
        var rows: [Row] = []
        var current = Row()
        for subview in subviews {
            let size = subview.sizeThatFits(.unspecified)
            let projected = current.elements.isEmpty ? size.width : current.width + horizontalSpacing + size.width
            if !current.elements.isEmpty, projected > maxWidth {
                rows.append(current)
                current = Row()
            }
            current.width = current.elements.isEmpty ? size.width : current.width + horizontalSpacing + size.width
            current.height = max(current.height, size.height)
            current.elements.append(Element(subview: subview, size: size))
        }
        if !current.elements.isEmpty {
            rows.append(current)
        }
        return rows
    }
}
