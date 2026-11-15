from __future__ import annotations

import urllib.parse
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlmodel import Session, select

from app.db import engine, init_db
from app.models import Product, ProductHistory, ProductStatus, ScrapeRun


def make_svg(brand: str, model: str, category: str, c1: str, c2: str, icon: str = "shoe") -> str:
    """Generate self-contained vector SVG data-URI. Never fails network requests."""
    icons = {
        "shoe": (
            f'<path d="M80 240 C90 200, 140 180, 200 190 C240 196, 280 180, 310 200 '
            f'C325 210, 330 230, 320 245 C290 255, 120 260, 80 240 Z" fill="white" fill-opacity="0.9"/>'
            f'<path d="M100 240 C140 230, 240 230, 315 242 C300 252, 220 254, 100 248 Z" fill="{c2}" fill-opacity="0.4"/>'
        ),
        "cleat": (
            '<path d="M75 235 C85 195, 135 175, 195 185 C235 192, 285 170, 315 195 '
            'C330 208, 330 225, 320 240 C290 248, 120 252, 75 235 Z" fill="white" fill-opacity="0.9"/>'
            '<circle cx="110" cy="250" r="4" fill="#fbbf24" />'
            '<circle cx="140" cy="252" r="4" fill="#fbbf24" />'
            '<circle cx="270" cy="248" r="4" fill="#fbbf24" />'
            '<circle cx="300" cy="245" r="4" fill="#fbbf24" />'
        ),
        "racquet": (
            '<ellipse cx="200" cy="160" rx="65" ry="80" fill="none" stroke="white" stroke-width="8" stroke-opacity="0.9"/>'
            '<line x1="160" y1="160" x2="240" y2="160" stroke="white" stroke-width="2" stroke-opacity="0.5"/>'
            '<line x1="200" y1="100" x2="200" y2="220" stroke="white" stroke-width="2" stroke-opacity="0.5"/>'
            '<line x1="200" y1="240" x2="200" y2="310" stroke="white" stroke-width="10" stroke-linecap="round" stroke-opacity="0.9"/>'
        ),
    }
    icon_svg = icons.get(icon, icons["shoe"])
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%">
  <defs>
    <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
  </defs>
  <rect width="400" height="400" fill="url(#g)"/>
  <rect x="20" y="20" width="360" height="360" rx="20" fill="none" stroke="white" stroke-opacity="0.12" stroke-width="2"/>
  <g transform="translate(0, -10)">
    {icon_svg}
  </g>
  <rect x="28" y="28" width="96" height="28" rx="14" fill="black" fill-opacity="0.25"/>
  <text x="76" y="47" font-family="system-ui, -apple-system, sans-serif" font-size="12" font-weight="700" fill="white" text-anchor="middle" letter-spacing="1">{brand.upper()}</text>
  <text x="200" y="325" font-family="system-ui, -apple-system, sans-serif" font-size="16" font-weight="700" fill="white" text-anchor="middle">{model}</text>
  <text x="200" y="348" font-family="system-ui, -apple-system, sans-serif" font-size="12" fill="white" fill-opacity="0.75" text-anchor="middle">{category}</text>
</svg>"""
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


SAMPLE_PRODUCTS = [
    {
        "id": 1001,
        "slug": "tenis-nike-revolution-6-next-nature",
        "url": "https://www.tivolli.com.br/1001-tenis-nike-revolution-6-next-nature",
        "name": "Tênis Nike Revolution 6 Next Nature Masculino",
        "codigo": "DC3728-003",
        "price": Decimal("279.99"),
        "price_boleto": Decimal("251.99"),
        "installments": {"count": 6, "value": 46.66, "interest_free": True},
        "sizes": ["38", "39", "40", "41", "42", "43"],
        "available": True,
        "description": "O Nike Revolution 6 Next Nature oferece conforto com espuma macia para amortecer sua passada. Ideal para corrida e caminhada.",
        "images": [make_svg("Nike", "Revolution 6", "Running Masculino", "#3b82f6", "#1d4ed8", "shoe")],
        "category_id": 144,
        "breadcrumbs": ["Calçados", "Running Masculino", "Tênis de Corrida"],
        "brand": "Nike",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1002,
        "slug": "tenis-nike-pegasus-40",
        "url": "https://www.tivolli.com.br/1002-tenis-nike-pegasus-40",
        "name": "Tênis Nike Air Zoom Pegasus 40",
        "codigo": "DV3853-100",
        "price": Decimal("489.90"),
        "price_boleto": Decimal("440.91"),
        "installments": {"count": 10, "value": 48.99, "interest_free": True},
        "sizes": ["39", "40", "41", "42"],
        "available": True,
        "description": "Uma passada elástica para qualquer corrida com amortecimento responsivo Zoom Air.",
        "images": [make_svg("Nike", "Pegasus 40", "Running Masculino", "#059669", "#047857", "shoe")],
        "category_id": 144,
        "breadcrumbs": ["Calçados", "Running Masculino", "Tênis de Corrida"],
        "brand": "Nike",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1003,
        "slug": "chuteira-nike-mercurial-vapor-15-club-campo",
        "url": "https://www.tivolli.com.br/1003-chuteira-nike-mercurial-vapor-15-club-campo",
        "name": "Chuteira Nike Mercurial Vapor 15 Club Campo",
        "codigo": "DJ5963-001",
        "price": Decimal("299.90"),
        "price_boleto": Decimal("269.91"),
        "installments": {"count": 6, "value": 49.98, "interest_free": True},
        "sizes": ["38", "39", "40", "41", "42"],
        "available": True,
        "description": "Velocidade explosiva no gramado com textura aderente em todo o cabedal.",
        "images": [make_svg("Nike", "Mercurial Vapor 15", "Chuteiras Campo", "#ea580c", "#c2410c", "cleat")],
        "category_id": 93,
        "breadcrumbs": ["Futebol", "Chuteiras Para Campo"],
        "brand": "Nike",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1004,
        "slug": "chuteira-nike-phantom-gx-academy-society",
        "url": "https://www.tivolli.com.br/1004-chuteira-nike-phantom-gx-academy-society",
        "name": "Chuteira Nike Phantom GX Academy Society",
        "codigo": "DD9476-600",
        "price": Decimal("389.90"),
        "price_boleto": Decimal("350.91"),
        "installments": {"count": 8, "value": 48.73, "interest_free": True},
        "sizes": ["39", "40", "41", "42", "43"],
        "available": True,
        "description": "Controle de bola preciso em gramados sintéticos com tecnologia NikeSkin.",
        "images": [make_svg("Nike", "Phantom GX", "Chuteiras Society", "#7c3aed", "#6d28d9", "cleat")],
        "category_id": 94,
        "breadcrumbs": ["Futebol", "Chuteiras Society"],
        "brand": "Nike",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1005,
        "slug": "tenis-adidas-runfalcon-3",
        "url": "https://www.tivolli.com.br/1005-tenis-adidas-runfalcon-3",
        "name": "Tênis Adidas Runfalcon 3.0",
        "codigo": "HP7544",
        "price": Decimal("249.99"),
        "price_boleto": Decimal("224.99"),
        "installments": {"count": 5, "value": 49.99, "interest_free": True},
        "sizes": ["37", "38", "39", "40", "41", "42"],
        "available": True,
        "description": "Tênis leve para corrida e treino diário com entressola Cloudfoam macia.",
        "images": [make_svg("Adidas", "Runfalcon 3.0", "Running Shoes", "#2563eb", "#1e40af", "shoe")],
        "category_id": 144,
        "breadcrumbs": ["Calçados", "Running Masculino", "Tênis de Corrida"],
        "brand": "Adidas",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1006,
        "slug": "tenis-adidas-duramo-speed",
        "url": "https://www.tivolli.com.br/1006-tenis-adidas-duramo-speed",
        "name": "Tênis Adidas Duramo Speed Masculino",
        "codigo": "IE7262",
        "price": Decimal("349.90"),
        "price_boleto": Decimal("314.91"),
        "installments": {"count": 7, "value": 49.98, "interest_free": True},
        "sizes": ["39", "40", "41", "42", "43"],
        "available": True,
        "description": "Amortecimento Lightstrike superleve para corridas rápidas e dinâmicas.",
        "images": [make_svg("Adidas", "Duramo Speed", "Running Shoes", "#0891b2", "#0e7490", "shoe")],
        "category_id": 144,
        "breadcrumbs": ["Calçados", "Running Masculino", "Tênis de Corrida"],
        "brand": "Adidas",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1007,
        "slug": "tenis-asics-gel-contend-8",
        "url": "https://www.tivolli.com.br/1007-tenis-asics-gel-contend-8",
        "name": "Tênis Asics Gel-Contend 8",
        "codigo": "1011B492-001",
        "price": Decimal("299.90"),
        "price_boleto": Decimal("269.91"),
        "installments": {"count": 6, "value": 49.98, "interest_free": True},
        "sizes": ["38", "39", "40", "41", "42", "43"],
        "available": True,
        "description": "Amortecimento GEL confiável e ajuste perfeito para corredores iniciantes e intermediários.",
        "images": [make_svg("Asics", "Gel-Contend 8", "Running Shoes", "#4f46e5", "#3730a3", "shoe")],
        "category_id": 144,
        "breadcrumbs": ["Calçados", "Running Masculino", "Tênis de Corrida"],
        "brand": "Asics",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1008,
        "slug": "raquete-de-tenis-yonex-ezone-100",
        "url": "https://www.tivolli.com.br/1008-raquete-de-tenis-yonex-ezone-100",
        "name": "Raquete de Tênis Yonex EZONE 100 (300g)",
        "codigo": "07EZ100",
        "price": Decimal("1499.00"),
        "price_boleto": Decimal("1349.10"),
        "installments": {"count": 12, "value": 124.91, "interest_free": True},
        "sizes": ["L2", "L3", "L4"],
        "available": True,
        "description": "Excelente potência e sensação suave com formato de cabeça ISOMETRIC da Yonex.",
        "images": [make_svg("Yonex", "EZONE 100", "Raquetes de Tênis", "#0284c7", "#0369a1", "racquet")],
        "category_id": 92,
        "breadcrumbs": ["Tênis", "Raquetes de Tênis", "Yonex"],
        "brand": "Yonex",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1009,
        "slug": "raquete-de-tenis-yonex-vcore-98",
        "url": "https://www.tivolli.com.br/1009-raquete-de-tenis-yonex-vcore-98",
        "name": "Raquete de Tênis Yonex VCORE 98 (305g)",
        "codigo": "07VC98",
        "price": Decimal("1599.00"),
        "price_boleto": Decimal("1439.10"),
        "installments": {"count": 12, "value": 133.25, "interest_free": True},
        "sizes": ["L2", "L3"],
        "available": True,
        "description": "Máximo spin e precisão para jogadores avançados com tecnologia 2G-Namd Flex Force.",
        "images": [make_svg("Yonex", "VCORE 98", "Raquetes de Tênis", "#dc2626", "#b91c1c", "racquet")],
        "category_id": 92,
        "breadcrumbs": ["Tênis", "Raquetes de Tênis", "Yonex"],
        "brand": "Yonex",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1010,
        "slug": "tenis-puma-flyer-runner",
        "url": "https://www.tivolli.com.br/1010-tenis-puma-flyer-runner",
        "name": "Tênis Puma Flyer Runner Unissex",
        "codigo": "192257-01",
        "price": Decimal("199.90"),
        "price_boleto": Decimal("179.91"),
        "installments": {"count": 4, "value": 49.97, "interest_free": True},
        "sizes": ["36", "37", "38", "39", "40", "41", "42"],
        "available": True,
        "description": "Estilo moderno e palmilha SoftFoam+ para conforto a cada passo.",
        "images": [make_svg("Puma", "Flyer Runner", "Running Shoes", "#18181b", "#27272a", "shoe")],
        "category_id": 144,
        "breadcrumbs": ["Calçados", "Running Masculino", "Tênis de Corrida"],
        "brand": "Puma",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1011,
        "slug": "tenis-olympikus-corre-3",
        "url": "https://www.tivolli.com.br/1011-tenis-olympikus-corre-3",
        "name": "Tênis Olympikus Corre 3",
        "codigo": "43513229",
        "price": Decimal("399.90"),
        "price_boleto": Decimal("359.91"),
        "installments": {"count": 8, "value": 49.98, "interest_free": True},
        "sizes": ["38", "39", "40", "41", "42", "43"],
        "available": True,
        "description": "O tênis oficial do corredor brasileiro com tecnologia Eleva Pro e solado Gripper.",
        "images": [make_svg("Olympikus", "Corre 3", "Running Shoes", "#15803d", "#166534", "shoe")],
        "category_id": 144,
        "breadcrumbs": ["Calçados", "Running Masculino", "Tênis de Corrida"],
        "brand": "Olympikus",
        "status": ProductStatus.ACTIVE,
    },
    {
        "id": 1012,
        "slug": "chuteira-adidas-predator-accuracy-campo",
        "url": "https://www.tivolli.com.br/1012-chuteira-adidas-predator-accuracy-campo",
        "name": "Chuteira Adidas Predator Accuracy.3 Campo",
        "codigo": "GW4588",
        "price": Decimal("429.90"),
        "price_boleto": Decimal("386.91"),
        "installments": {"count": 8, "value": 53.73, "interest_free": True},
        "sizes": ["39", "40", "41", "42"],
        "available": False,
        "description": "Precisão absoluta no chute com textura High Definition Grip no cabedal têxtil.",
        "images": [make_svg("Adidas", "Predator Accuracy", "Chuteiras Campo", "#b91c1c", "#991b1b", "cleat")],
        "category_id": 93,
        "breadcrumbs": ["Futebol", "Chuteiras Para Campo"],
        "brand": "Adidas",
        "status": ProductStatus.OUT_OF_STOCK,
    },
]


# Deterministic demo price history: (days ago, factor of today's price), oldest first.
_HISTORY_SHAPES = [
    [(60, 1.18), (45, 1.12), (30, 1.12), (14, 1.05), (3, 1.0)],
    [(60, 0.92), (40, 0.95), (21, 1.0), (7, 1.0)],
    [(55, 1.25), (35, 1.2), (20, 1.1), (6, 1.1), (1, 1.0)],
]


def _seed_history(session: Session, now: datetime) -> None:
    """Replace demo history so charts and the chat's price-history answers have data."""
    for index, item in enumerate(SAMPLE_PRODUCTS):
        if item.get("price") is None:
            continue
        for old in session.exec(select(ProductHistory).where(ProductHistory.product_id == item["id"])).all():
            session.delete(old)
        for days, factor in _HISTORY_SHAPES[index % len(_HISTORY_SHAPES)]:
            price = (Decimal(item["price"]) * Decimal(str(factor))).quantize(Decimal("0.01"))
            session.add(
                ProductHistory(
                    product_id=item["id"], price=price, available=True, scraped_at=now - timedelta(days=days)
                )
            )


def seed_database(force: bool = False) -> int:
    init_db()
    with Session(engine, expire_on_commit=False) as session:
        now = datetime.now(UTC)
        for item in SAMPLE_PRODUCTS:
            existing = session.get(Product, item["id"])
            if existing:
                for k, v in item.items():
                    setattr(existing, k, v)
                existing.updated_at = now
                session.add(existing)
            else:
                p = Product(**item, scraped_at=now, created_at=now, updated_at=now)
                session.add(p)

        session.flush()
        _seed_history(session, now)

        # Record a successful scrape run so stats and health check show last_refresh
        run = ScrapeRun(
            run_type="seed",
            started_at=now,
            completed_at=now,
            products_scraped=len(SAMPLE_PRODUCTS),
            products_failed=0,
            products_disappeared=0,
            status="completed",
        )
        session.add(run)
        session.commit()
        print(f"Successfully seeded {len(SAMPLE_PRODUCTS)} products with self-contained vector graphics.")
        return len(SAMPLE_PRODUCTS)


if __name__ == "__main__":
    seed_database(force=True)
