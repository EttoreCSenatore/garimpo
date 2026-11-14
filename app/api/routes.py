from __future__ import annotations

import re
import time
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urljoin
from uuid import uuid4

import httpx
from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlmodel import Session, String, and_, cast, func, or_, select

from app.api.dependencies import get_db, get_splunk, require_admin
from app.config import settings
from app.models import Category, Product, ProductHistory, ProductStatus, ScrapeRun
from app.search.intent_parser import ParsedIntent, parse_intent
from app.security import chat_rate_limit, image_rate_limit, safe_http_url
from app.splunk_hec import SplunkHECLogger
from app.state import MAX_INFLIGHT_SINGLE, active_workers, inflight_single, spawn

router = APIRouter()


# ---------------------------------------------------------------------------
# Chat models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=settings.chat_max_message_length)
    session_id: str | None = Field(default=None, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class ChatResponse(BaseModel):
    reply: str
    filters_applied: dict
    products: list[dict]

hot_product_cache: TTLCache = TTLCache(maxsize=settings.hot_product_cache_size, ttl=60)

# Estado das sessões de chat para o fluxo de compra guiado (em memória, por
# session_id). Guarda preferências pessoais (gênero, número do calçado) que
# persistem entre as mensagens da mesma conversa.
chat_sessions: OrderedDict[str, dict] = OrderedDict()
SESSION_TTL_SECONDS = 900


class ProductResponse(BaseModel):
    id: int
    slug: str
    url: str
    name: str
    codigo: str | None = None
    currency: str
    price: Decimal | None = None
    price_boleto: Decimal | None = None
    installments: dict | None = None
    sizes: list[str] = []
    available: bool
    description: str | None = None
    images: list[str] = []
    category_id: int | None = None
    breadcrumbs: list[str] = []
    brand: str | None = None
    status: ProductStatus
    scraped_at: datetime


class CategoryResponse(BaseModel):
    id: int
    slug: str
    url: str
    name: str | None = None
    product_count: int


class PaginatedResponse(BaseModel):
    items: list
    next_cursor: str | None = None
    total: int | None = None


def _like(term: str) -> str:
    """Escape LIKE wildcards so user input is matched literally (use with escape="\\")."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _cache_headers() -> dict[str, str]:
    return {"Cache-Control": f"public, max-age={settings.cache_ttl_seconds}"}


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _apply_disclaimer(product: dict) -> dict:
    if settings.disclaimer:
        product["price_disclaimer"] = "indicative"
        product["source_url"] = product.get("url")
    return product


@router.get("/", tags=["health"])
@router.get("/api/", tags=["health"])
@router.get("/api/health", tags=["health"])
async def health_check(db: Session = Depends(get_db)):
    last_run = db.exec(
        select(ScrapeRun)
        .where(ScrapeRun.completed_at.is_not(None))
        .order_by(ScrapeRun.completed_at.desc())
        .limit(1)
    ).first()
    return {
        "status": "ok",
        "service": "tivolli-scraper",
        "version": "1.0.0",
        "last_refresh": last_run.completed_at.isoformat() if last_run and last_run.completed_at else None,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/products", tags=["products"])
async def list_products(
    response: Response,
    category_id: int | None = None,
    brand: str | None = None,
    min_price: Decimal | None = None,
    max_price: Decimal | None = None,
    available: bool | None = None,
    q: str | None = Query(default=None, max_length=100),
    cursor: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    statement = select(Product)
    count_stmt = select(func.count(Product.id))

    if category_id is not None:
        statement = statement.where(Product.category_id == category_id)
        count_stmt = count_stmt.where(Product.category_id == category_id)
    if brand is not None:
        statement = statement.where(Product.brand == brand)
        count_stmt = count_stmt.where(Product.brand == brand)
    if min_price is not None:
        statement = statement.where(Product.price >= min_price)
        count_stmt = count_stmt.where(Product.price >= min_price)
    if max_price is not None:
        statement = statement.where(Product.price <= max_price)
        count_stmt = count_stmt.where(Product.price <= max_price)
    if available is not None:
        statement = statement.where(Product.available == available)
        count_stmt = count_stmt.where(Product.available == available)
    if q:
        like = _like(q)
        statement = statement.where(Product.name.ilike(like, escape="\\"))
        count_stmt = count_stmt.where(Product.name.ilike(like, escape="\\"))

    total = db.exec(count_stmt).one()

    if cursor is not None:
        statement = statement.where(Product.id > cursor)
    statement = statement.order_by(Product.id).limit(limit)

    products = db.exec(statement).all()
    items = []
    for p in products:
        data = _apply_disclaimer(p.model_dump())
        items.append(data)

    next_cursor = str(products[-1].id) if len(products) == limit else None
    response.headers.update(_cache_headers())
    return {"items": items, "next_cursor": next_cursor, "total": total}


@router.get("/products/{product_id}", tags=["products"])
async def get_product(
    product_id: int,
    response: Response,
    db: Session = Depends(get_db),
    splunk: SplunkHECLogger = Depends(get_splunk),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    # Atomic increment (no read-modify-write race between concurrent requests).
    db.execute(update(Product).where(Product.id == product_id).values(view_count=Product.view_count + 1))
    db.commit()
    db.refresh(product)

    stale = (
        product.scraped_at is not None
        and (datetime.now(UTC) - _as_utc(product.scraped_at)).total_seconds() > 300
    )
    if stale and product_id not in inflight_single and len(inflight_single) < MAX_INFLIGHT_SINGLE:
        from app.tasks import refresh_single_product_async

        inflight_single.add(product_id)
        spawn(refresh_single_product_async(product_id))

    data = product.model_dump()
    hot_product_cache[product_id] = data
    response.headers.update(_cache_headers())
    return _apply_disclaimer(data)


@router.get("/products/{product_id}/history", tags=["products"])
async def get_product_history(
    product_id: int,
    response: Response,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    statement = (
        select(ProductHistory)
        .where(ProductHistory.product_id == product_id)
        .order_by(ProductHistory.scraped_at.desc())
        .limit(limit)
    )
    history = db.exec(statement).all()
    response.headers.update(_cache_headers())
    return {"product_id": product_id, "history": [h.model_dump() for h in history]}


@router.get("/categories", tags=["categories"])
async def list_categories(response: Response, db: Session = Depends(get_db)):
    statement = select(Category).order_by(Category.name)
    categories = db.exec(statement).all()
    response.headers.update(_cache_headers())
    return {
        "items": [
            CategoryResponse(
                id=c.id,
                slug=c.slug,
                url=c.url,
                name=c.name,
                product_count=c.product_count,
            ).model_dump()
            for c in categories
        ]
    }


@router.get("/stats", tags=["stats"])
async def get_stats(response: Response, db: Session = Depends(get_db)):
    total_products = db.exec(select(func.count(Product.id))).one()
    active_products = db.exec(
        select(func.count(Product.id)).where(Product.status == ProductStatus.ACTIVE)
    ).one()

    since = datetime.now(UTC) - timedelta(hours=24)
    runs_24h = db.exec(
        select(ScrapeRun).where(ScrapeRun.started_at >= since)
    ).all()

    total_scraped = sum(r.products_scraped for r in runs_24h)
    total_failed = sum(r.products_failed for r in runs_24h)
    success_rate = (
        (total_scraped / (total_scraped + total_failed) * 100)
        if (total_scraped + total_failed) > 0
        else 100.0
    )

    last_run = db.exec(
        select(ScrapeRun)
        .where(ScrapeRun.completed_at.is_not(None))
        .order_by(ScrapeRun.completed_at.desc())
        .limit(1)
    ).first()

    response.headers.update(_cache_headers())
    return {
        "total_products": total_products,
        "active_products": active_products,
        "last_run": last_run.completed_at.isoformat() if last_run and last_run.completed_at else None,
        "last_run_status": last_run.status if last_run else None,
        "success_rate_24h": round(success_rate, 2),
        "errors_24h": total_failed,
        "runs_24h": len(runs_24h),
    }


@router.post("/admin/refresh", tags=["admin"])
async def trigger_full_refresh(
    _: str = Depends(require_admin),
    splunk: SplunkHECLogger = Depends(get_splunk),
):
    from app.tasks import run_full_refresh_async

    spawn(run_full_refresh_async())
    await splunk.send({"event_type": "tivolli.run.manual_trigger", "run_type": "full"})
    return {"status": "started", "message": "Atualização completa iniciada"}


@router.post("/admin/refresh/{product_id}", tags=["admin"])
async def refresh_single_product(
    product_id: int,
    _: str = Depends(require_admin),
    splunk: SplunkHECLogger = Depends(get_splunk),
):
    from app.tasks import refresh_single_product_async

    if product_id not in inflight_single:
        inflight_single.add(product_id)
        spawn(refresh_single_product_async(product_id))
    await splunk.send(
        {"event_type": "tivolli.run.manual_trigger", "run_type": "single", "product_id": product_id}
    )
    return {"status": "started", "message": f"Atualização iniciada para o produto {product_id}"}




@router.get("/admin/queue", tags=["admin"])
async def get_queue_status(_: str = Depends(require_admin)):
    return {
        "active_workers": active_workers,
        "cache_size": len(hot_product_cache),
        "cache_max": settings.hot_product_cache_size,
    }


_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/avif"}
_MAX_REDIRECTS = 3


def _sniff_image_type(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head[:4] == b"GIF8":
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


@router.get("/api/image-proxy", tags=["products"], dependencies=[Depends(image_rate_limit)])
async def proxy_image(url: str = Query(..., max_length=2048)):
    """Proxy a product image from an allow-listed shop host.

    Hardened against SSRF: https/http only, allow-listed hosts (no IP literals),
    every redirect hop re-validated, response size capped, and only raster image
    types are returned (no SVG/HTML).
    """
    allowed = settings.image_host_list
    current = safe_http_url(url, allowed)
    if current is None:
        raise HTTPException(status_code=400, detail="URL de imagem não permitida")

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            for _ in range(_MAX_REDIRECTS + 1):
                async with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        nxt = safe_http_url(urljoin(current, resp.headers.get("location", "")), allowed)
                        if nxt is None:
                            raise HTTPException(status_code=502, detail="Redirecionamento não permitido")
                        current = nxt
                        continue
                    if resp.status_code != 200:
                        raise HTTPException(status_code=502, detail="Falha ao buscar imagem")

                    declared = resp.headers.get("content-length")
                    if declared and declared.isdigit() and int(declared) > settings.image_proxy_max_bytes:
                        raise HTTPException(status_code=502, detail="Imagem muito grande")

                    body = bytearray()
                    async for chunk in resp.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > settings.image_proxy_max_bytes:
                            raise HTTPException(status_code=502, detail="Imagem muito grande")

                    declared_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    content_type = declared_type if declared_type in _IMAGE_TYPES else _sniff_image_type(bytes(body[:16]))
                    if content_type is None:
                        raise HTTPException(status_code=502, detail="Conteúdo não é uma imagem suportada")
                    return Response(
                        content=bytes(body),
                        media_type=content_type,
                        headers={"Cache-Control": "public, max-age=86400"},
                    )
            raise HTTPException(status_code=502, detail="Muitos redirecionamentos")
    except HTTPException:
        raise
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Erro ao buscar imagem") from exc


# ---------------------------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------------------------

# Portuguese labels for category slugs, used in the chat replies
CATEGORY_LABELS = {
    "running": "corrida",
    "futebol": "futebol",
    "tenis": "tênis",
    "basquete": "basquete",
    "natacao": "natação",
    "academia": "treino",
    "caminhada": "caminhada",
    "volei": "vôlei",
}

# Rótulos de gênero usados nas respostas do chat
GENDER_LABELS = {
    "masculino": "para **homem**",
    "feminino": "para **mulher**",
    "infantil": "**infantil**",
    "unissex": "**unissex**",
}


def _get_chat_session(session_id: str | None) -> dict:
    """Recupera (ou cria) a sessão de chat em memória para um session_id."""
    key = session_id or uuid4().hex
    now = time.monotonic()
    # The dict is ordered by last use, so expired sessions are always at the front.
    while chat_sessions and now - next(iter(chat_sessions.values()))["ts"] > SESSION_TTL_SECONDS:
        chat_sessions.popitem(last=False)
    # Cap the store so a flood of random session ids cannot exhaust memory.
    while key not in chat_sessions and len(chat_sessions) >= settings.chat_max_sessions:
        chat_sessions.popitem(last=False)
    session = chat_sessions.get(key)
    if session is None or now - session["ts"] > SESSION_TTL_SECONDS:
        session = {"prefs": {}, "declined": {}, "awaiting": None, "last_intent": None, "ts": now}
        chat_sessions[key] = session
    session["ts"] = now
    chat_sessions.move_to_end(key)
    return session


def _gender_condition(gender: str):
    """Condição SQL para o gênero pedido.

    Usa radicais ("masculin", "feminin") para casar tanto "Feminino" quanto
    "Feminina". Produtos sem marcador de gênero no nome são considerados
    unissex e continuam aparecendo; apenas os de gênero conflitante são
    excluídos.
    """
    if gender == "infantil":
        return or_(Product.name.ilike("%infantil%"), Product.name.ilike("%jr%"))
    stems = {
        "masculino": "%masculin%",
        "feminino": "%feminin%",
        "unissex": "%unissex%",
    }
    like = stems.get(gender, f"%{gender}%")
    conflicting = [c for c in ("%masculin%", "%feminin%", "%infantil%") if c != like]
    not_conflicting = and_(
        *[~Product.name.ilike(g) for g in conflicting]
    )
    return or_(Product.name.ilike(like), not_conflicting)


def _size_condition(size: int):
    """Condição SQL para o número do calçado.

    `sizes` é uma lista JSON; o elemento é casado entre aspas ("38") para
    não confundir 38 com 138.
    """
    return cast(Product.sizes, String).ilike(f'%"{size}"%')


def _filters_applied(intent: ParsedIntent, prefs: dict) -> dict:
    """Resume os filtros da busca (do intent + preferências pessoais)."""
    filters: dict = {}
    if intent.category_keywords:
        filters["category"] = intent.category_keywords
    if intent.brand:
        filters["brand"] = intent.brand
    if intent.price_max is not None:
        filters["price_max"] = intent.price_max
    if intent.price_min is not None:
        filters["price_min"] = intent.price_min
    if intent.available:
        filters["available"] = True
    if prefs.get("gender"):
        filters["gender"] = prefs["gender"]
    if prefs.get("size"):
        filters["size"] = prefs["size"]
    return filters


# Palavras muito comuns que não ajudam a buscar produtos
_STOPWORDS = {
    "quero", "gostaria", "procurando", "procuro", "preciso", "mostrar",
    "mostre", "ver", "tem", "temos", "tudo", "todos", "todas", "produto",
    "produtos", "item", "itens", "loja", "site", "algum", "alguma",
    "alguns", "algumas", "para", "com", "sem", "por", "que", "onde",
    "quais", "qual", "sobre", "entre", "até", "ate", "abaixo", "acima",
    "under", "below", "above", "over", "from", "between", "max", "min",
    "de", "do", "da", "dos", "das", "no", "na", "nos", "nas", "em",
    "um", "uma", "uns", "umas", "os", "as", "e", "ou", "ao", "aos",
    "à", "às", "me", "meu", "minha", "você", "voce", "vocês", "voces",
    "tamanho", "tamanhos", "número", "numero", "num", "calço", "calco",
    "masculino", "masculina", "masculinas", "feminino", "feminina",
    "femininas", "infantil", "unissex", "unisex", "homem", "homens",
    "mulher", "mulheres", "menino", "menina", "meninos", "meninas",
    "criança", "crianca", "crianças", "criancas", "ele", "ela", "how",
    "the", "for", "and", "any", "show", "find", "oi", "olá", "ola",
    "bom", "boa", "dia", "tarde", "noite", "hey", "hello",
}


def _stem(word: str) -> str:
    """Singular simples: "bolas" -> "bola" (amplia o casamento por substring)."""
    return word[:-1] if len(word) > 4 and word.endswith("s") else word


def _content_words(message: str) -> list[str]:
    """Palavras de conteúdo da mensagem (sem stopwords), para busca livre."""
    words = re.findall(r"[a-zà-ÿ]+", message.lower())
    seen: set[str] = set()
    terms: list[str] = []
    for word in words:
        if len(word) < 3 or word in _STOPWORDS:
            continue
        stem = _stem(word)
        if stem not in seen:
            seen.add(stem)
            terms.append(stem)
    return terms[:5]


def _free_terms(message: str, intent: ParsedIntent) -> list[str]:
    """Palavras de conteúdo que o parser não reconheceu.

    Servem para refinar a busca com vocabulário livre — por exemplo, o nome
    do time em "camisa do flamengo" vira o termo extra "flamengo".
    """
    recognized = {_stem(k) for k in intent.keywords}
    if intent.brand:
        recognized.add(_stem(intent.brand.lower()))
    return [t for t in _content_words(message) if t not in recognized]


@router.post("/api/chat", tags=["chat"], response_model=ChatResponse, dependencies=[Depends(chat_rate_limit)])
async def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
) -> ChatResponse:
    """
    Aceita uma mensagem em linguagem natural, extrai os filtros de busca via
    intent parser, consulta o banco e devolve uma resposta conversacional
    com os produtos correspondentes.

    Preferências pessoais (gênero, número do calçado) ficam lembradas por
    sessão; quando faltam numa busca de calçados, o bot pergunta antes de
    pesquisar.
    """
    intent = parse_intent(payload.message)

    # --- Estado da sessão: preferências persistem entre mensagens ---------
    session = _get_chat_session(payload.session_id)
    prefs: dict = session["prefs"]
    declined: dict = session["declined"]

    has_product_criteria = bool(
        intent.category_keywords
        or intent.brand
        or intent.price_min is not None
        or intent.price_max is not None
    )

    # Resposta numérica direta à pergunta do número (ex.: "38")
    if session.get("awaiting") == "size" and intent.size is None:
        m = re.fullmatch(r"\s*(\d{1,2})\s*", payload.message)
        if m and 16 <= int(m.group(1)) <= 50:
            intent.size = int(m.group(1))

    if intent.gender:
        prefs["gender"] = intent.gender
        declined["gender"] = False
    if intent.size:
        prefs["size"] = intent.size
        declined["size"] = False
    if intent.skip_preferences:
        declined[session.get("awaiting") or "gender"] = True

    # Palavras livres da mensagem (ex.: time "flamengo") refinam a busca.
    # Numa resposta a uma pergunta anterior, reutiliza as da busca original.
    if has_product_criteria:
        session["free_terms"] = _free_terms(payload.message, intent)
    free_terms: list[str] = session.get("free_terms") or []

    # Uma mensagem sem critérios de produto é resposta a uma pergunta
    # anterior (ou informação pessoal extra) — reutiliza os últimos filtros.
    if not has_product_criteria and session.get("last_intent"):
        intent = session["last_intent"]

    # --- Fluxo guiado: pergunta o que falta antes de pesquisar ------------
    # Gênero vale para calçados e vestuário; o número do pé, só para calçados.
    # Buscas neutras (bolas, raquetes, acessórios) não recebem perguntas.
    ask_gender = (
        intent.is_gendered_search
        and not prefs.get("gender")
        and not declined.get("gender")
    )
    ask_size = (
        intent.is_footwear_search
        and not prefs.get("size")
        and not declined.get("size")
    )

    if ask_gender:
        session["last_intent"] = intent
        session["awaiting"] = "gender"
        return ChatResponse(
            reply=(
                "Claro! Para quem é? Me diga **masculino**, "
                "**feminino**, **infantil** ou **tanto faz**."
            ),
            filters_applied=_filters_applied(intent, prefs),
            products=[],
        )
    if ask_size:
        session["last_intent"] = intent
        session["awaiting"] = "size"
        return ChatResponse(
            reply=(
                "Anotado! E qual número você calça? (ex.: **38**) "
                "— se não importar, digite **tanto faz**."
            ),
            filters_applied=_filters_applied(intent, prefs),
            products=[],
        )

    session["awaiting"] = None
    if has_product_criteria:
        session["last_intent"] = intent

    statement = select(Product)

    # --- Category filter ---------------------------------------------------
    # Busca pelos slugs de categoria mapeados (ex.: "futebol"), pelas
    # palavras-chave digitadas (ex.: "chuteira") e, quando o parser não
    # reconheceu nada, pelas próprias palavras da mensagem (ex.: "flamengo")
    # — assim produtos de qualquer tipo da loja são encontráveis.
    search_terms: list[str] = list(
        dict.fromkeys(intent.category_keywords + intent.keywords)
    )
    extra_terms: list[str] = free_terms
    if (
        not search_terms
        and not free_terms
        and intent.brand is None
        and intent.price_min is None
        and intent.price_max is None
    ):
        # Mensagem sem termos úteis (ex.: saudação): mostra o catálogo geral
        pass
    elif not search_terms and intent.brand is None and intent.price_min is None and intent.price_max is None:
        # Nada reconhecido: as palavras da mensagem viram os termos de busca
        search_terms = free_terms
        extra_terms = []
    if search_terms:
        category_conditions = []
        for kw in search_terms:
            like_kw = f"%{kw}%"
            category_conditions.append(cast(Product.breadcrumbs, String).ilike(like_kw))
            category_conditions.append(Product.name.ilike(like_kw))
            category_conditions.append(Product.slug.ilike(like_kw))

        # Also try matching category via joined Category slug
        cat_ids = db.exec(
            select(Category.id).where(
                or_(*[Category.slug.ilike(f"%{s}%") for s in search_terms])
            )
        ).all()
        if cat_ids:
            category_conditions.append(Product.category_id.in_(cat_ids))

        if category_conditions:
            statement = statement.where(or_(*category_conditions))

    # --- Brand filter ------------------------------------------------------
    if intent.brand:
        statement = statement.where(Product.brand.ilike(f"%{intent.brand}%"))

    # --- Price filters -----------------------------------------------------
    if intent.price_min is not None:
        statement = statement.where(Product.price >= Decimal(str(intent.price_min)))
    if intent.price_max is not None:
        statement = statement.where(Product.price <= Decimal(str(intent.price_max)))

    # --- Availability filter -----------------------------------------------
    if intent.available is not None:
        statement = statement.where(Product.available == intent.available)

    # --- Filtros de preferências pessoais -----------------------------------
    # O gênero só filtra produtos com versões de gênero (calçados e roupas);
    # o número do pé só faz sentido para calçados.
    if prefs.get("gender") and intent.is_gendered_search:
        statement = statement.where(_gender_condition(prefs["gender"]))

    base_statement = statement

    if prefs.get("size") and intent.is_footwear_search:
        statement = statement.where(_size_condition(prefs["size"]))

    # Termos livres (ex.: time) estreitam a busca com um AND; se nada
    # sobrar, a busca é refeita sem eles lá embaixo.
    if extra_terms:
        extra_conditions = []
        for term in extra_terms:
            like = f"%{term}%"
            extra_conditions.append(Product.name.ilike(like))
            extra_conditions.append(Product.slug.ilike(like))
            extra_conditions.append(cast(Product.breadcrumbs, String).ilike(like))
        statement = statement.where(or_(*extra_conditions))

    # Limit results returned to the chat
    statement = statement.order_by(Product.view_count.desc()).limit(24)
    products = db.exec(statement).all()

    # Sem resultados: relaxa primeiro os termos extras, depois o número
    terms_relaxed = False
    size_relaxed = False
    if not products and extra_terms:
        terms_relaxed = True
        relaxed = base_statement.order_by(Product.view_count.desc()).limit(24)
        products = db.exec(relaxed).all()
    if not products and prefs.get("size") and intent.is_footwear_search:
        size_relaxed = True
        relaxed = base_statement.order_by(Product.view_count.desc()).limit(24)
        products = db.exec(relaxed).all()

    # --- Build conversational reply ---------------------------------------
    count = len(products)
    filters_applied = _filters_applied(intent, prefs)
    if extra_terms:
        filters_applied["terms"] = extra_terms

    if count == 0:
        reply = (
            "Não encontrei nenhum produto correspondente. "
            "Tente buscar com termos mais amplos ou outra marca!"
        )
    else:
        parts: list[str] = [f"Encontrei {count} produto{'s' if count != 1 else ''}"]

        if intent.category_keywords:
            cat_label = " / ".join(CATEGORY_LABELS.get(k, k) for k in intent.category_keywords)
            parts.append(f"de **{cat_label}**")
        if intent.brand:
            parts.append(f"da marca **{intent.brand}**")
        if prefs.get("gender"):
            parts.append(GENDER_LABELS.get(prefs["gender"], f"para **{prefs['gender']}**"))
        if prefs.get("size") and not size_relaxed:
            parts.append(f"no **número {prefs['size']}**")
        if intent.price_max is not None:
            parts.append(f"abaixo de **R$ {intent.price_max:,.0f}**")
        if intent.price_min is not None:
            parts.append(f"acima de **R$ {intent.price_min:,.0f}**")
        if intent.available:
            parts.append("com **estoque disponível**")

        if len(parts) == 1:
            reply = f"Aqui estão {count} opções encontradas para você:"
        else:
            reply = " ".join(parts) + ". Veja as melhores opções:"

        if size_relaxed:
            reply += (
                f" Não encontrei opções no número {prefs['size']}, "
                "então incluí todos os tamanhos."
            )
        if terms_relaxed:
            reply += (
                f" Não encontrei nada com \"{' '.join(extra_terms)}\", "
                "então ampliei a busca."
            )

    return ChatResponse(
        reply=reply,
        filters_applied=filters_applied,
        products=[_apply_disclaimer(p.model_dump()) for p in products],
    )
