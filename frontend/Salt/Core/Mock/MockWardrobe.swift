enum MockWardrobe {
    static let items: [WardrobeItem] = [
        WardrobeItem(
            id: "coat",
            title: "Wool overcoat",
            brand: "COS",
            size: "M",
            condition: "Good",
            pricePence: 7500,
            kind: .outerwear,
            listedOn: [.vinted, .depop, .ebay],
            pendingOffer: nil
        ),
        WardrobeItem(
            id: "levis",
            title: "Levi's 501s",
            brand: "Levi's",
            size: "W28 L30",
            condition: "Good",
            pricePence: 4500,
            kind: .bottom,
            listedOn: [.vinted, .ebay],
            pendingOffer: PendingOffer(pence: 3500, marketplace: .vinted)
        ),
        WardrobeItem(
            id: "knit",
            title: "Cream cable knit",
            brand: "Arket",
            size: "M",
            condition: "Excellent",
            pricePence: 2800,
            kind: .top,
            listedOn: [.vinted, .depop],
            pendingOffer: nil
        ),
        WardrobeItem(
            id: "slip",
            title: "Silk slip dress",
            brand: "& Other Stories",
            size: "8",
            condition: "Excellent",
            pricePence: 2200,
            kind: .dress,
            listedOn: [.depop],
            pendingOffer: nil
        ),
        WardrobeItem(
            id: "flats",
            title: "Leather ballet flats",
            brand: "Repetto",
            size: "38",
            condition: "Excellent",
            pricePence: 4000,
            kind: .shoes,
            listedOn: [.depop, .ebay],
            pendingOffer: nil
        ),
        WardrobeItem(
            id: "linen",
            title: "Linen trousers",
            brand: "Arket",
            size: "12",
            condition: "Excellent",
            pricePence: 2600,
            kind: .bottom,
            listedOn: [.vinted, .ebay],
            pendingOffer: nil
        ),
        WardrobeItem(
            id: "breton",
            title: "Striped Breton top",
            brand: "Saint James",
            size: "S",
            condition: "Good",
            pricePence: 1800,
            kind: .top,
            listedOn: [.vinted],
            pendingOffer: nil
        ),
        WardrobeItem(
            id: "tee",
            title: "Vintage band tee",
            brand: "Fruit of the Loom",
            size: "M",
            condition: "Fair",
            pricePence: 1500,
            kind: .top,
            listedOn: [.vinted, .depop],
            pendingOffer: nil
        )
    ]
}
