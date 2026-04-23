"""
Mock Shopify product data for development/testing.
Covers the full spectrum of audit outcomes — critical failures, partial passes, and near-perfect products.
"""

MOCK_PRODUCTS = [
    # ── Product 1: Near-perfect ────────────────────────────────────────────────
    {
        "id": 1001,
        "title": "Premium Merino Wool Crew Neck Sweater",
        "handle": "premium-merino-wool-crew-neck-sweater",
        "body_html": """<p>Experience unparalleled warmth and softness with our Premium Merino Wool Crew Neck Sweater. Crafted from 100% ethically sourced merino wool from New Zealand, this sweater offers exceptional temperature regulation, keeping you comfortable in both cool and mild weather.</p>
<ul>
<li>100% Merino wool — naturally odour-resistant and moisture-wicking</li>
<li>Ribbed cuffs and hem for a tailored, flattering fit</li>
<li>Available in 8 colours and sizes XS through 3XL</li>
<li>Machine washable on gentle cycle — easy care for everyday wear</li>
<li>Ethically produced in Portugal under fair trade conditions</li>
</ul>
<p>Perfect for layering under a blazer or wearing on its own, this versatile sweater transitions effortlessly from office to weekend. The classic crew neck silhouette flatters every body type, while the fine-gauge knit keeps the profile slim and modern.</p>
<p>Each sweater is finished with our signature label and comes gift-ready in a recycled cotton pouch. Free UK shipping on orders over £50.</p>""",
        "status": "active",
        "product_type": "Knitwear",
        "vendor": "NordicThread",
        "tags": "merino, wool, sweater, knitwear, winter, sustainable, crew-neck, premium",
        "seo": {
            "title": "Premium Merino Wool Crew Neck Sweater | NordicThread",
            "description": "Shop our 100% merino wool crew neck sweater. Ethically sourced, machine washable, available in 8 colours. Free UK shipping over £50.",
        },
        "images": [
            {"id": 101, "alt": "Premium merino wool sweater in navy — front view"},
            {"id": 102, "alt": "Premium merino wool sweater — back view showing ribbed detail"},
            {"id": 103, "alt": "Close-up of merino wool texture and quality"},
            {"id": 104, "alt": "Model wearing sweater with chinos for casual office look"},
        ],
        "variants": [
            {"id": 201, "price": "89.99", "compare_at_price": "120.00",
             "inventory_management": "shopify", "inventory_quantity": 45},
        ],
        "options": [{"name": "Size", "values": ["XS", "S", "M", "L", "XL", "2XL"]}],
    },

    # ── Product 2: Missing everything ─────────────────────────────────────────
    {
        "id": 1002,
        "title": "New Product",
        "handle": "new-product",
        "body_html": "",
        "status": "active",
        "product_type": "",
        "vendor": "",
        "tags": "",
        "seo": {"title": "", "description": ""},
        "images": [],
        "variants": [
            {"id": 202, "price": "0.00", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 0},
        ],
        "options": [{"name": "Title", "values": ["Default Title"]}],
    },

    # ── Product 3: Thin description, no meta ──────────────────────────────────
    {
        "id": 1003,
        "title": "Leather Bifold Wallet",
        "handle": "leather-bifold-wallet",
        "body_html": "<p>Premium leather wallet. Holds up to 8 cards.</p>",
        "status": "active",
        "product_type": "Accessories",
        "vendor": "CraftLeather Co",
        "tags": "wallet, leather, accessories",
        "seo": {"title": "", "description": ""},
        "images": [
            {"id": 103, "alt": None},
        ],
        "variants": [
            {"id": 203, "price": "45.00", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 23},
        ],
        "options": [{"name": "Colour", "values": ["Black", "Brown", "Tan"]}],
    },

    # ── Product 4: Good content, single image ─────────────────────────────────
    {
        "id": 1004,
        "title": "Bamboo Cutting Board — Extra Large",
        "handle": "bamboo-cutting-board-extra-large",
        "body_html": """<p>Our extra-large bamboo cutting board is the centrepiece of any serious kitchen. Measuring 45cm x 30cm, it provides ample workspace for meal prep, meat carving, vegetable chopping, and bread slicing — all on one sustainably sourced surface.</p>
<p>Bamboo is naturally antimicrobial, harder than maple, and grows back in 3–5 years compared to 50+ years for traditional hardwoods. Every board is hand-finished with food-grade mineral oil for a smooth, splinter-free surface that protects your knives.</p>
<ul>
<li>Dimensions: 45cm x 30cm x 2cm</li>
<li>100% Moso bamboo — sustainably harvested</li>
<li>Juice groove around the perimeter catches runoff</li>
<li>Non-slip rubber feet keep the board stable</li>
<li>Hand wash recommended — do not submerge</li>
</ul>""",
        "status": "active",
        "product_type": "Kitchen",
        "vendor": "GreenKitchen",
        "tags": "bamboo, cutting-board, kitchen, sustainable, eco-friendly, chef",
        "seo": {
            "title": "Extra Large Bamboo Cutting Board 45x30cm | GreenKitchen",
            "description": "Professional-grade extra large bamboo cutting board with juice groove and non-slip feet. Sustainably sourced, knife-friendly.",
        },
        "images": [
            {"id": 104, "alt": "Extra large bamboo cutting board on kitchen counter"},
        ],
        "variants": [
            {"id": 204, "price": "34.99", "compare_at_price": "49.99",
             "inventory_management": "shopify", "inventory_quantity": 67},
        ],
        "options": [{"name": "Title", "values": ["Default Title"]}],
    },

    # ── Product 5: Missing alt text on some images ────────────────────────────
    {
        "id": 1005,
        "title": "Ceramic Pour-Over Coffee Set",
        "handle": "ceramic-pour-over-coffee-set",
        "body_html": """<p>Elevate your morning ritual with our handcrafted ceramic pour-over coffee set. Each piece is wheel-thrown by artisan potters in our Bristol studio, meaning no two sets are exactly alike. The set includes a dripper, carafe, and two matching cups.</p>
<p>The dripper's wide-cone design promotes even extraction, bringing out the nuanced flavours of specialty coffee. The matte glaze is food-safe, dishwasher-safe, and develops a beautiful patina over time. The carafe holds 600ml — perfect for two generous cups.</p>
<ul>
<li>Hand-thrown stoneware — made in Bristol, UK</li>
<li>Wide-cone dripper for even extraction</li>
<li>600ml borosilicate carafe included</li>
<li>Two 200ml cups included</li>
<li>Compatible with size 4 paper filters</li>
<li>Dishwasher safe — microwave safe</li>
</ul>""",
        "status": "active",
        "product_type": "Coffee",
        "vendor": "BristolCeramics",
        "tags": "coffee, pour-over, ceramic, handmade, artisan, gift",
        "seo": {
            "title": "Handcrafted Ceramic Pour-Over Coffee Set | Bristol Ceramics",
            "description": "Hand-thrown ceramic pour-over set made in Bristol. Includes dripper, 600ml carafe and 2 cups. Each piece unique.",
        },
        "images": [
            {"id": 105, "alt": "Ceramic pour-over coffee set arranged on white marble"},
            {"id": 106, "alt": None},
            {"id": 107, "alt": "Detail of hand-thrown texture on ceramic dripper"},
            {"id": 108, "alt": None},
        ],
        "variants": [
            {"id": 205, "price": "68.00", "compare_at_price": "85.00",
             "inventory_management": "shopify", "inventory_quantity": 12},
        ],
        "options": [{"name": "Colour", "values": ["Ash Grey", "Cream", "Slate Blue"]}],
    },

    # ── Product 6: Published, zero inventory ──────────────────────────────────
    {
        "id": 1006,
        "title": "Vintage Brass Desk Lamp",
        "handle": "vintage-brass-desk-lamp",
        "body_html": """<p>Our Vintage Brass Desk Lamp brings warmth and character to any workspace. Inspired by 1920s industrial design, the adjustable arm and weighted base make it as functional as it is beautiful. The Edison-style bulb (included) casts a warm, focused glow perfect for reading and detail work.</p>
<ul>
<li>Solid brass construction — naturally develops a patina over time</li>
<li>Adjustable arm extends 45cm from base</li>
<li>360-degree rotating head for precise light direction</li>
<li>Compatible with E27 bulbs up to 60W or LED equivalent</li>
<li>4m fabric-wrapped cord with inline switch</li>
<li>UK 3-pin plug included</li>
</ul>
<p>Each lamp is individually inspected before shipping. Weight: 1.8kg. Base diameter: 15cm. A timeless piece that improves with age.</p>""",
        "status": "active",
        "product_type": "Lighting",
        "vendor": "BrassworkStudio",
        "tags": "lamp, desk-lamp, brass, vintage, industrial, lighting, office",
        "seo": {
            "title": "Vintage Brass Desk Lamp | BrassworkStudio",
            "description": "Solid brass adjustable desk lamp with Edison bulb. Inspired by 1920s industrial design. UK plug included, free delivery.",
        },
        "images": [
            {"id": 109, "alt": "Vintage brass desk lamp illuminated on oak desk"},
            {"id": 110, "alt": "Brass desk lamp arm detail showing adjustment joint"},
            {"id": 111, "alt": "Lamp base and fabric cord close-up"},
        ],
        "variants": [
            {"id": 206, "price": "129.99", "compare_at_price": "160.00",
             "inventory_management": "shopify", "inventory_quantity": 0},
        ],
        "options": [{"name": "Title", "values": ["Default Title"]}],
    },

    # ── Product 7: No tags, no product type ───────────────────────────────────
    {
        "id": 1007,
        "title": "Stainless Steel Water Bottle 750ml",
        "handle": "stainless-steel-water-bottle-750ml",
        "body_html": """<p>Stay hydrated all day with our 750ml stainless steel water bottle. Double-wall vacuum insulation keeps drinks cold for 24 hours and hot for 12 hours. The wide-mouth opening fits ice cubes and is easy to clean by hand or in the dishwasher.</p>
<p>Made from 18/8 food-grade stainless steel with no BPA, BPS, or phthalates. The powder-coated exterior resists scratches and slipping. The leak-proof lid includes a carry loop for clipping to a bag or backpack.</p>
<ul>
<li>750ml capacity — ideal for all-day hydration</li>
<li>Double-wall vacuum insulation</li>
<li>Cold 24h / Hot 12h performance</li>
<li>18/8 food-grade stainless steel</li>
<li>BPA-free, BPS-free, phthalate-free</li>
<li>Dishwasher safe lid — hand wash bottle recommended</li>
</ul>""",
        "status": "active",
        "product_type": "",
        "vendor": "HydraFlow",
        "tags": "",
        "seo": {
            "title": "750ml Stainless Steel Water Bottle | HydraFlow",
            "description": "Double-wall vacuum insulated 750ml water bottle. Cold 24h, hot 12h. BPA-free, dishwasher-safe lid.",
        },
        "images": [
            {"id": 112, "alt": "Stainless steel water bottle in forest green"},
            {"id": 113, "alt": "Water bottle open showing wide mouth opening"},
            {"id": 114, "alt": "Bottle and lid disassembled for cleaning"},
        ],
        "variants": [
            {"id": 207, "price": "28.00", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 89},
        ],
        "options": [
            {"name": "Colour", "values": ["Forest Green", "Midnight Black", "Slate Grey", "Desert Rose"]},
        ],
    },

    # ── Product 8: Duplicate description (same as product 9) ─────────────────
    {
        "id": 1008,
        "title": "Cotton Canvas Tote Bag — Small",
        "handle": "cotton-canvas-tote-bag-small",
        "body_html": "<p>Our cotton canvas tote bag is perfect for everyday shopping and errands. Made from 100% organic cotton canvas with reinforced handles. Available in natural and black. Reusable and machine washable.</p>",
        "status": "active",
        "product_type": "Bags",
        "vendor": "EcoCarry",
        "tags": "tote, canvas, bag, eco-friendly, reusable, cotton",
        "seo": {
            "title": "Cotton Canvas Tote Bag Small | EcoCarry",
            "description": "100% organic cotton canvas tote bag. Reinforced handles, machine washable. Perfect everyday shopping bag.",
        },
        "images": [
            {"id": 115, "alt": "Small cotton canvas tote bag in natural colour"},
            {"id": 116, "alt": "Tote bag interior showing capacity"},
        ],
        "variants": [
            {"id": 208, "price": "12.99", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 150},
        ],
        "options": [{"name": "Colour", "values": ["Natural", "Black"]}],
    },

    # ── Product 9: Duplicate description (same as product 8) ─────────────────
    {
        "id": 1009,
        "title": "Cotton Canvas Tote Bag — Large",
        "handle": "cotton-canvas-tote-bag-large",
        "body_html": "<p>Our cotton canvas tote bag is perfect for everyday shopping and errands. Made from 100% organic cotton canvas with reinforced handles. Available in natural and black. Reusable and machine washable.</p>",
        "status": "active",
        "product_type": "Bags",
        "vendor": "EcoCarry",
        "tags": "tote, canvas, bag, eco-friendly, reusable, cotton",
        "seo": {
            "title": "Cotton Canvas Tote Bag Large | EcoCarry",
            "description": "100% organic cotton canvas tote bag. Reinforced handles, machine washable. Perfect everyday shopping bag.",
        },
        "images": [
            {"id": 117, "alt": "Large cotton canvas tote bag in natural colour"},
            {"id": 118, "alt": "Tote bag with groceries inside showing capacity"},
            {"id": 119, "alt": "Handle detail showing double-stitched reinforcement"},
        ],
        "variants": [
            {"id": 209, "price": "18.99", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 95},
        ],
        "options": [{"name": "Colour", "values": ["Natural", "Black", "Navy"]}],
    },

    # ── Product 10: Title too long SEO, no compare-at ─────────────────────────
    {
        "id": 1010,
        "title": "Hand-Poured Soy Wax Candle with Essential Oils",
        "handle": "hand-poured-soy-wax-candle-essential-oils",
        "body_html": """<p>Transform your space with our hand-poured soy wax candles, crafted in small batches in our Edinburgh studio. Each candle is scented with pure essential oils — never synthetic fragrances — for a clean, therapeutic burn that fills the room without overpowering it.</p>
<p>The natural soy wax burns cooler and cleaner than paraffin, producing minimal soot and lasting up to 50 hours on a single pour. The reusable glass vessel can be cleaned and repurposed as a drinking glass, vase, or storage jar once the candle is finished.</p>
<ul>
<li>200g natural soy wax — vegan and cruelty-free</li>
<li>Scented with 100% pure essential oils</li>
<li>Cotton wick — no lead or zinc</li>
<li>Burns up to 50 hours</li>
<li>Reusable glass vessel — 8cm diameter</li>
<li>Hand-poured in Edinburgh in batches of 12</li>
</ul>
<p>Available in Lavender & Eucalyptus, Cedarwood & Bergamot, and Wild Rose & Geranium. Each scent is carefully balanced by our in-house aromatherapist.</p>""",
        "status": "active",
        "product_type": "Home Fragrance",
        "vendor": "EdinburghWick",
        "tags": "candle, soy, essential-oils, handmade, vegan, gift, home-fragrance, edinburgh",
        "seo": {
            "title": "Hand-Poured Soy Wax Candle with Pure Essential Oils — Vegan — Edinburgh Studio — 50 Hour Burn Time",
            "description": "Hand-poured soy wax candles scented with pure essential oils. Vegan, 50-hour burn, reusable glass. Made in Edinburgh.",
        },
        "images": [
            {"id": 120, "alt": "Soy wax candle burning on rustic wooden table"},
            {"id": 121, "alt": "Three candle scents arranged — lavender, cedarwood, rose"},
            {"id": 122, "alt": "Close-up of candle label and glass vessel"},
            {"id": 123, "alt": "Candle with dried botanicals as styling props"},
        ],
        "variants": [
            {"id": 210, "price": "22.00", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 34},
        ],
        "options": [
            {"name": "Scent", "values": ["Lavender & Eucalyptus", "Cedarwood & Bergamot", "Wild Rose & Geranium"]},
        ],
    },

    # ── Product 11: Short SEO title, few tags ─────────────────────────────────
    {
        "id": 1011,
        "title": "Recycled Denim Patchwork Jacket",
        "handle": "recycled-denim-patchwork-jacket",
        "body_html": """<p>No two jackets are alike. Our patchwork denim jackets are handmade from reclaimed denim offcuts sourced from UK garment manufacturers, diverting textile waste from landfill and turning it into a genuinely one-of-a-kind piece.</p>
<p>Each jacket takes approximately 6 hours to construct in our Manchester workshop. The patchwork technique gives each piece a unique colour story — some cool and indigo-heavy, others washed and faded with character. The fit is relaxed and unisex, styled to wear open over a hoodie or belted over a dress.</p>
<ul>
<li>Made from 100% reclaimed denim offcuts</li>
<li>Fully lined with recycled polyester</li>
<li>Two chest pockets, two side pockets</li>
<li>Unisex sizing — runs slightly large, size down if between sizes</li>
<li>Hand wash cold — do not tumble dry</li>
<li>Each jacket is photographed individually — what you see is what you get</li>
</ul>""",
        "status": "active",
        "product_type": "Outerwear",
        "vendor": "ReThread",
        "tags": "denim, jacket, upcycled, sustainable",
        "seo": {
            "title": "Denim Jacket",
            "description": "Handmade recycled denim patchwork jacket. One-of-a-kind, made in Manchester from reclaimed offcuts.",
        },
        "images": [
            {"id": 124, "alt": "Recycled denim patchwork jacket front view"},
            {"id": 125, "alt": "Jacket back detail showing patchwork pattern"},
            {"id": 126, "alt": "Model wearing jacket belted over a dress"},
        ],
        "variants": [
            {"id": 211, "price": "185.00", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 8},
        ],
        "options": [{"name": "Size", "values": ["XS", "S", "M", "L", "XL"]}],
    },

    # ── Product 12: Decent but no compare-at, not charm-priced ───────────────
    {
        "id": 1012,
        "title": "Oak Wood Floating Wall Shelf",
        "handle": "oak-wood-floating-wall-shelf",
        "body_html": """<p>Add warmth and natural character to any room with our solid oak floating wall shelf. Each shelf is hand-finished with a hard-wax oil that enhances the wood's natural grain while providing a durable, water-resistant surface.</p>
<p>The hidden bracket system means no visible fixings — just a clean, seamless float from the wall. The shelf comes with all fixings included, and the bracket accommodates both stud and plasterboard walls with the supplied wall plugs.</p>
<ul>
<li>Solid European oak — FSC certified sustainable source</li>
<li>Available in three lengths: 60cm, 90cm, 120cm</li>
<li>20cm depth — suitable for books, plants, and decorative objects</li>
<li>Hidden bracket system — no visible fixings</li>
<li>Hard-wax oil finish — water-resistant and food-safe</li>
<li>Weight capacity: 15kg per shelf</li>
<li>All wall fixings included</li>
</ul>""",
        "status": "active",
        "product_type": "Furniture",
        "vendor": "OakAndWood",
        "tags": "shelf, oak, floating-shelf, furniture, interior, wall-storage, solid-wood",
        "seo": {
            "title": "Solid Oak Floating Wall Shelf | OakAndWood",
            "description": "FSC-certified solid oak floating shelf with hidden brackets. 3 sizes, hard-wax oil finish. All fixings included.",
        },
        "images": [
            {"id": 127, "alt": "Oak floating shelf mounted with books and plant"},
            {"id": 128, "alt": "Shelf detail showing wood grain and finish"},
            {"id": 129, "alt": "Three shelf sizes shown for scale comparison"},
            {"id": 130, "alt": "Bracket system detail before installation"},
        ],
        "variants": [
            {"id": 212, "price": "65.00", "compare_at_price": None,
             "inventory_management": "shopify", "inventory_quantity": 22},
        ],
        "options": [{"name": "Length", "values": ["60cm", "90cm", "120cm"]}],
    },
]

MOCK_SHOP = {
    "name": "Demo Store",
    "email": "demo@shopiq.dev",
    "domain": "demo.myshopify.com",
    "plan_name": "basic",
    "currency": "GBP",
    "country": "GB",
}

MOCK_SHOP_DOMAIN = "demo.myshopify.com"


# ── Mock orders (90-day window with realistic refund patterns) ─────────────────

MOCK_ORDERS = [
    # ── Refunded: size/fit ─────────────────────────────────────────────────────
    {
        "id": 5001, "name": "#1001", "email": "alice@example.com",
        "created_at": "2024-02-10T10:00:00+00:00",
        "financial_status": "refunded", "total_price": "89.00", "currency": "GBP",
        "customer": {"id": 101, "first_name": "Alice", "last_name": "Brown", "email": "alice@example.com"},
        "line_items": [{"id": 901, "product_id": 1001, "title": "Premium Merino Wool Crew Neck Sweater", "quantity": 1, "price": "89.00", "handle": "premium-merino-wool-crew-neck-sweater", "image": {"src": None}}],
        "refunds": [{"id": 801, "created_at": "2024-02-15T10:00:00+00:00", "reason": "customer", "note": "Too large, doesn't fit properly", "refund_line_items": [{"id": 701, "line_item_id": 901, "quantity": 1, "subtotal": "89.00"}]}],
    },
    # ── Refunded: wrong item ───────────────────────────────────────────────────
    {
        "id": 5002, "name": "#1002", "email": "bob@example.com",
        "created_at": "2024-02-12T11:00:00+00:00",
        "financial_status": "refunded", "total_price": "45.00", "currency": "GBP",
        "customer": {"id": 102, "first_name": "Bob", "last_name": "Smith", "email": "bob@example.com"},
        "line_items": [{"id": 902, "product_id": 1003, "title": "Full-Grain Leather Bifold Wallet", "quantity": 1, "price": "45.00", "handle": "leather-bifold-wallet", "image": {"src": None}}],
        "refunds": [{"id": 802, "created_at": "2024-02-14T09:00:00+00:00", "reason": "inventory", "note": "Received wrong colour — ordered black, got brown", "refund_line_items": [{"id": 702, "line_item_id": 902, "quantity": 1, "subtotal": "45.00"}]}],
    },
    # ── Refunded: damaged ─────────────────────────────────────────────────────
    {
        "id": 5003, "name": "#1003", "email": "carol@example.com",
        "created_at": "2024-02-18T14:00:00+00:00",
        "financial_status": "refunded", "total_price": "120.00", "currency": "GBP",
        "customer": {"id": 103, "first_name": "Carol", "last_name": "Jones", "email": "carol@example.com"},
        "line_items": [{"id": 903, "product_id": 1006, "title": "Vintage Brass Desk Lamp", "quantity": 1, "price": "120.00", "handle": "vintage-brass-desk-lamp", "image": {"src": None}}],
        "refunds": [{"id": 803, "created_at": "2024-02-20T08:00:00+00:00", "reason": "other", "note": "Arrived broken — cracked shade and bent arm", "refund_line_items": [{"id": 703, "line_item_id": 903, "quantity": 1, "subtotal": "120.00"}]}],
    },
    # ── Refunded: size/fit again (repeat customer flagged) ────────────────────
    {
        "id": 5004, "name": "#1004", "email": "alice@example.com",
        "created_at": "2024-02-22T09:00:00+00:00",
        "financial_status": "refunded", "total_price": "89.00", "currency": "GBP",
        "customer": {"id": 101, "first_name": "Alice", "last_name": "Brown", "email": "alice@example.com"},
        "line_items": [{"id": 904, "product_id": 1001, "title": "Premium Merino Wool Crew Neck Sweater", "quantity": 1, "price": "89.00", "handle": "premium-merino-wool-crew-neck-sweater", "image": {"src": None}}],
        "refunds": [{"id": 804, "created_at": "2024-02-25T10:00:00+00:00", "reason": "customer", "note": "Still too small — sizing runs very small", "refund_line_items": [{"id": 704, "line_item_id": 904, "quantity": 1, "subtotal": "89.00"}]}],
    },
    # ── Refunded: quality ─────────────────────────────────────────────────────
    {
        "id": 5005, "name": "#1005", "email": "dave@example.com",
        "created_at": "2024-03-01T10:00:00+00:00",
        "financial_status": "refunded", "total_price": "28.00", "currency": "GBP",
        "customer": {"id": 104, "first_name": "Dave", "last_name": "Wilson", "email": "dave@example.com"},
        "line_items": [{"id": 905, "product_id": 1008, "title": "EcoCarry Small Tote Bag", "quantity": 1, "price": "28.00", "handle": "ecocarry-small-tote", "image": {"src": None}}],
        "refunds": [{"id": 805, "created_at": "2024-03-04T12:00:00+00:00", "reason": "customer", "note": "Poor quality — stitching came apart after one use", "refund_line_items": [{"id": 705, "line_item_id": 905, "quantity": 1, "subtotal": "28.00"}]}],
    },
    # ── Refunded: not needed ──────────────────────────────────────────────────
    {
        "id": 5006, "name": "#1006", "email": "eve@example.com",
        "created_at": "2024-03-05T15:00:00+00:00",
        "financial_status": "refunded", "total_price": "38.00", "currency": "GBP",
        "customer": {"id": 105, "first_name": "Eve", "last_name": "Taylor", "email": "eve@example.com"},
        "line_items": [{"id": 906, "product_id": 1007, "title": "HydraFlow 750ml Insulated Water Bottle", "quantity": 1, "price": "38.00", "handle": "hydraflow-750ml-insulated-water-bottle", "image": {"src": None}}],
        "refunds": [{"id": 806, "created_at": "2024-03-07T09:00:00+00:00", "reason": "customer", "note": "Changed mind, no longer needed", "refund_line_items": [{"id": 706, "line_item_id": 906, "quantity": 1, "subtotal": "38.00"}]}],
    },
    # ── Fulfilled (no refund) ─────────────────────────────────────────────────
    {"id": 5007, "name": "#1007", "email": "frank@example.com", "created_at": "2024-02-08T10:00:00+00:00", "financial_status": "paid", "total_price": "65.00", "currency": "GBP", "customer": {"id": 106, "first_name": "Frank", "last_name": "Lee", "email": "frank@example.com"}, "line_items": [{"id": 907, "product_id": 1012, "title": "Solid Oak Floating Shelf", "quantity": 1, "price": "65.00", "handle": "solid-oak-floating-shelf", "image": {"src": None}}], "refunds": []},
    {"id": 5008, "name": "#1008", "email": "grace@example.com", "created_at": "2024-02-14T11:00:00+00:00", "financial_status": "paid", "total_price": "55.00", "currency": "GBP", "customer": {"id": 107, "first_name": "Grace", "last_name": "Kim", "email": "grace@example.com"}, "line_items": [{"id": 908, "product_id": 1005, "title": "Handcrafted Ceramic Pour-Over Set", "quantity": 1, "price": "55.00", "handle": "handcrafted-ceramic-pour-over-set", "image": {"src": None}}], "refunds": []},
    {"id": 5009, "name": "#1009", "email": "henry@example.com", "created_at": "2024-02-20T13:00:00+00:00", "financial_status": "paid", "total_price": "38.00", "currency": "GBP", "customer": {"id": 108, "first_name": "Henry", "last_name": "Evans", "email": "henry@example.com"}, "line_items": [{"id": 909, "product_id": 1007, "title": "HydraFlow 750ml Insulated Water Bottle", "quantity": 1, "price": "38.00", "handle": "hydraflow-750ml", "image": {"src": None}}], "refunds": []},
    {"id": 5010, "name": "#1010", "email": "iris@example.com", "created_at": "2024-02-25T09:00:00+00:00", "financial_status": "paid", "total_price": "45.00", "currency": "GBP", "customer": {"id": 109, "first_name": "Iris", "last_name": "Clark", "email": "iris@example.com"}, "line_items": [{"id": 910, "product_id": 1010, "title": "Hand-Poured Soy Wax Candle", "quantity": 2, "price": "22.50", "handle": "hand-poured-soy-wax-candle", "image": {"src": None}}], "refunds": []},
    {"id": 5011, "name": "#1011", "email": "jack@example.com", "created_at": "2024-03-02T14:00:00+00:00", "financial_status": "paid", "total_price": "89.00", "currency": "GBP", "customer": {"id": 110, "first_name": "Jack", "last_name": "White", "email": "jack@example.com"}, "line_items": [{"id": 911, "product_id": 1001, "title": "Premium Merino Wool Crew Neck Sweater", "quantity": 1, "price": "89.00", "handle": "premium-merino-wool-crew-neck-sweater", "image": {"src": None}}], "refunds": []},
    {"id": 5012, "name": "#1012", "email": "kate@example.com", "created_at": "2024-03-08T10:00:00+00:00", "financial_status": "paid", "total_price": "35.00", "currency": "GBP", "customer": {"id": 111, "first_name": "Kate", "last_name": "Hall", "email": "kate@example.com"}, "line_items": [{"id": 912, "product_id": 1004, "title": "Extra Large Bamboo Cutting Board", "quantity": 1, "price": "35.00", "handle": "extra-large-bamboo-cutting-board", "image": {"src": None}}], "refunds": []},
    {"id": 5013, "name": "#1013", "email": "liam@example.com", "created_at": "2024-03-10T16:00:00+00:00", "financial_status": "paid", "total_price": "185.00", "currency": "GBP", "customer": {"id": 112, "first_name": "Liam", "last_name": "Young", "email": "liam@example.com"}, "line_items": [{"id": 913, "product_id": 1011, "title": "Recycled Denim Patchwork Jacket", "quantity": 1, "price": "185.00", "handle": "recycled-denim-patchwork-jacket", "image": {"src": None}}], "refunds": []},
    {"id": 5014, "name": "#1014", "email": "mia@example.com", "created_at": "2024-03-12T11:00:00+00:00", "financial_status": "paid", "total_price": "28.00", "currency": "GBP", "customer": {"id": 113, "first_name": "Mia", "last_name": "Scott", "email": "mia@example.com"}, "line_items": [{"id": 914, "product_id": 1009, "title": "EcoCarry Large Tote Bag", "quantity": 1, "price": "28.00", "handle": "ecocarry-large-tote", "image": {"src": None}}], "refunds": []},
    {"id": 5015, "name": "#1015", "email": "noah@example.com", "created_at": "2024-03-14T09:00:00+00:00", "financial_status": "paid", "total_price": "45.00", "currency": "GBP", "customer": {"id": 114, "first_name": "Noah", "last_name": "Green", "email": "noah@example.com"}, "line_items": [{"id": 915, "product_id": 1003, "title": "Full-Grain Leather Bifold Wallet", "quantity": 1, "price": "45.00", "handle": "leather-bifold-wallet", "image": {"src": None}}], "refunds": []},
]
