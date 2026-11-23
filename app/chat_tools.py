"""Grounded chat tools: every answer is computed from the database, never invented.

Follow-up commands act on the products the previous search showed ("compare", "cheapest",
"price history"), so the chat feels like a conversation instead of one-shot search.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from sqlmodel import Session, select

from app.models import Product, ProductHistory

MAX_COMPARE = 4

_COMPARE_RE = re.compile(r"\b(compar\w*|versus|vs\.?|diferen[çc]a\w*|compare)\b", re.IGNORECASE)
_CHEAPEST_RE = re.compile(r"\b(mais barat\w*|cheapest|menor pre[çc]o|barat\w*)\b", re.IGNORECASE)
_DEALS_RE = re.compile(
    r"\b(ofertas?|promo[çc][õo]es|promo[çc][ãa]o|deals?|descontos?|liquida[çc][ãa]o|baixou de pre[çc]o)\b",
    re.IGNORECASE,
)
_HISTORY_RE = re.compile(
    r"\b(hist[óo]rico|baixou|caiu|subiu|varia[çc][ãa]o|price history|price drop|vale a pena)\b",
    re.IGNORECASE,
)
_COUNT_RE = re.compile(r"\b(\d)\s*(?:primeir\w*|first|op[çc][õo]es|produtos|itens)\b", re.IGNORECASE)
_WORD_COUNTS = {"dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4, "two": 2, "three": 3, "four": 4}


@dataclass
class Command:
    kind: str  # "compare" | "cheapest" | "history" | "deals"
    count: int = 3


def detect_command(message: str) -> Command | None:
    """Recognise a follow-up command; ``None`` means a normal product search."""
    text = message.strip()
    # A command is a short follow-up; a long sentence is almost certainly a new search.
    if len(text.split()) > 10:
        return None
    count = 3
    if m := _COUNT_RE.search(text):
        count = int(m.group(1))
    else:
        for word, value in _WORD_COUNTS.items():
            if re.search(rf"\b{word}\b", text, re.IGNORECASE):
                count = value
                break
    count = max(2, min(MAX_COMPARE, count))
    if _DEALS_RE.search(text):
        return Command("deals")
    if _COMPARE_RE.search(text):
        return Command("compare", count)
    if _HISTORY_RE.search(text):
        return Command("history")
    if _CHEAPEST_RE.search(text):
        return Command("cheapest")
    return None


def _brl(value: Decimal | float | None) -> str:
    if value is None:
        return "—"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def load_products(db: Session, ids: list[int]) -> list[Product]:
    """Products in the order of ``ids`` (missing ones are skipped)."""
    if not ids:
        return []
    rows = {p.id: p for p in db.exec(select(Product).where(Product.id.in_(ids))).all()}
    return [rows[i] for i in ids if i in rows]


def price_summary(db: Session, product: Product) -> dict:
    """Current, lowest and highest recorded price plus the change since the first record."""
    prices = [
        h.price
        for h in db.exec(
            select(ProductHistory).where(ProductHistory.product_id == product.id).order_by(ProductHistory.scraped_at)
        ).all()
        if h.price is not None
    ]
    current = product.price
    if current is not None and (not prices or prices[-1] != current):
        prices.append(current)
    summary: dict = {"id": product.id, "name": product.name, "current": current, "records": len(prices)}
    if prices:
        low, high = min(prices), max(prices)
        summary.update(lowest=low, highest=high)
        if len(prices) > 1 and prices[0]:
            summary["change_pct"] = round(float((prices[-1] - prices[0]) / prices[0] * 100), 1)
    return summary


def compare(products: list[Product]) -> dict:
    """Side-by-side table with the facts that decide a purchase."""
    priced = [p for p in products if p.price is not None]
    cheapest = min(priced, key=lambda p: p.price) if priced else None
    rows = [
        {
            "id": p.id,
            "name": p.name,
            "brand": p.brand,
            "price": p.price,
            "price_boleto": p.price_boleto,
            "installments": p.installments,
            "sizes": p.sizes,
            "available": p.available,
            "cheapest": cheapest is not None and p.id == cheapest.id,
        }
        for p in products
    ]
    return {"rows": rows, "cheapest_id": cheapest.id if cheapest else None}


def compare_reply(products: list[Product]) -> str:
    table = compare(products)
    lines = [f"Comparando os **{len(products)} primeiros** resultados:"]
    for row in table["rows"]:
        sizes = ", ".join(row["sizes"]) if row["sizes"] else "sem tamanhos disponíveis"
        flag = " (**mais barato**)" if row["cheapest"] else ""
        lines.append(f"• **{row['name']}**: {_brl(row['price'])}{flag}. Tamanhos: {sizes}.")
    priced = [r for r in table["rows"] if r["price"] is not None]
    if len(priced) > 1:
        gap = max(r["price"] for r in priced) - min(r["price"] for r in priced)
        lines.append(f"Diferença entre o mais caro e o mais barato: **{_brl(gap)}**.")
    return "\n".join(lines)


def cheapest_reply(products: list[Product]) -> tuple[str, list[Product]]:
    priced = sorted((p for p in products if p.price is not None and p.available), key=lambda p: p.price)
    if not priced:
        return "Nenhum dos resultados anteriores tem preço disponível em estoque.", []
    top = priced[:3]
    return f"Os mais baratos em estoque entre os resultados: o menor preço é **{_brl(top[0].price)}**.", top


def history_reply(db: Session, product: Product) -> str:
    s = price_summary(db, product)
    if s["records"] < 2 or "lowest" not in s:
        return (
            f"Ainda não tenho histórico suficiente de **{product.name}**: "
            f"preço atual {_brl(s['current'])}. O histórico cresce a cada nova coleta."
        )
    text = (
        f"**{product.name}**: preço atual {_brl(s['current'])}, "
        f"menor já registrado {_brl(s['lowest'])}, maior {_brl(s['highest'])}."
    )
    change = s.get("change_pct")
    if change is not None and change != 0:
        text += f" Variação desde o primeiro registro: **{change:+.1f}%**."
    if s["current"] is not None and s["current"] == s["lowest"]:
        text += " Está no **menor preço** que já vi."
    return text


def deals_reply(deals: list[dict]) -> str:
    if not deals:
        return "Ainda não encontrei quedas de preço reais no histórico. Volte depois de algumas coletas!"
    top = deals[0]
    return (
        f"Encontrei **{len(deals)} oferta{'s' if len(deals) != 1 else ''}** de verdade, calculadas pelo histórico de preços "
        f"(produtos no menor preço dos últimos {top['days']} dias). A maior queda: **{top['product'].name}**, "
        f"**-{top['discount_pct']:.0f}%** (de {_brl(top['was'])} por {_brl(top['now'])})."
    )
