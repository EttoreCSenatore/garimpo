from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlmodel import Session, and_, func, or_, select, cast, String

from app.api.dependencies import get_db, get_splunk, require_admin
from app.config import settings
from app.models import Category, Product, ProductHistory, ProductStatus, ScrapeRun
from app.search.intent_parser import ParsedIntent, parse_intent
from app.splunk_hec import SplunkHECLogger

router = APIRouter()


# ---------------------------------------------------------------------------
# Chat models
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    filters_applied: dict
    products: list[dict]

hot_product_cache: TTLCache = TTLCache(maxsize=settings.hot_product_cache_size, ttl=60)
active_workers: dict[str, int] = {"full": 0, "incremental": 0, "single": 0}

# Estado das sessões de chat para o fluxo de compra guiado (em memória, por
# session_id). Guarda preferências pessoais (gênero, número do calçado) que
# persistem entre as mensagens da mesma conversa.
chat_sessions: dict[str, dict] = {}
SESSION_TTL_SECONDS = 900


class ProductResponse(BaseModel):
    id: int
    slug: str
    url: str
    name: str
    codigo: Optional[str] = None
    currency: str
    price: Optional[Decimal] = None
    price_boleto: Optional[Decimal] = None
    installments: Optional[dict] = None
    sizes: list[str] = []
    available: bool
    description: Optional[str] = None
    images: list[str] = []
    category_id: Optional[int] = None
    breadcrumbs: list[str] = []
    brand: Optional[str] = None
    status: ProductStatus
    scraped_at: datetime


class CategoryResponse(BaseModel):
    id: int
    slug: str
    url: str
    name: Optional[str] = None
    product_count: int


class PaginatedResponse(BaseModel):
    items: list
    next_cursor: Optional[str] = None
    total: Optional[int] = None


def _cache_headers() -> dict[str, str]:
    return {"Cache-Control": f"public, max-age={settings.cache_ttl_seconds}"}


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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/products", tags=["products"])
async def list_products(
    response: Response,
    category_id: Optional[int] = None,
    brand: Optional[str] = None,
    min_price: Optional[Decimal] = None,
    max_price: Optional[Decimal] = None,
    available: Optional[bool] = None,
    q: Optional[str] = None,
    cursor: Optional[int] = None,
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
        like = f"%{q}%"
        statement = statement.where(Product.name.ilike(like))
        count_stmt = count_stmt.where(Product.name.ilike(like))

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
    cached = hot_product_cache.get(product_id)
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produto não encontrado")

    product.view_count += 1
    db.add(product)
    db.commit()
    db.refresh(product)

    if cached and (datetime.now(timezone.utc) - cached["scraped_at"]).total_seconds() < 300:
        response.headers.update(_cache_headers())
        return _apply_disclaimer(cached)

    data = product.model_dump()
    hot_product_cache[product_id] = data

    if product.scraped_at and (datetime.now(timezone.utc) - product.scraped_at).total_seconds() > 300:
        try:
            from app.tasks import refresh_single_product_async
            import asyncio
            asyncio.create_task(refresh_single_product_async(product_id))
        except Exception:
            pass

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

    since = datetime.now(timezone.utc) - timedelta(hours=24)
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
    import asyncio
    asyncio.create_task(run_full_refresh_async())
    await splunk.send({"event_type": "tivolli.run.manual_trigger", "run_type": "full"})
    return {"status": "started", "message": "Atualização completa iniciada"}


@router.post("/admin/refresh/{product_id}", tags=["admin"])
async def refresh_single_product(
    product_id: int,
    _: str = Depends(require_admin),
    splunk: SplunkHECLogger = Depends(get_splunk),
):
    from app.tasks import refresh_single_product_async
    import asyncio
    asyncio.create_task(refresh_single_product_async(product_id))
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


@router.get("/api/image-proxy", tags=["products"])
async def proxy_image(url: str):
    """
    Proxies product images to ensure correct MIME type (image/jpeg)
    and eliminate third-party browser network errors.
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="Falha ao buscar imagem")
            content_type = resp.headers.get("content-type", "")
            if not content_type or content_type == "application/octet-stream":
                content_type = "image/jpeg"
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Erro no proxy: {str(e)}")


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


def _get_chat_session(session_id: Optional[str]) -> dict:
    """Recupera (ou cria) a sessão de chat em memória para um session_id."""
    key = session_id or uuid4().hex
    now = time.monotonic()
    session = chat_sessions.get(key)
    if session is None or now - session["ts"] > SESSION_TTL_SECONDS:
        session = {"prefs": {}, "declined": {}, "awaiting": None, "last_intent": None, "ts": now}
        chat_sessions[key] = session
    session["ts"] = now
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


@router.post("/api/chat", tags=["chat"], response_model=ChatResponse)
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
