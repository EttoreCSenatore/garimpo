"""
Smart Intent Parser — pure-Python (regex + dict), no external LLM needed.
Translates natural-language queries (EN + PT-BR) into DB filter kwargs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Synonym / keyword maps
# ---------------------------------------------------------------------------

CATEGORY_SYNONYMS: dict[str, list[str]] = {
    "running": [
        "running", "corrida", "run", "runner", "correr",
        "jogging", "jog", "atletismo",
    ],
    "futebol": [
        "futebol", "soccer", "football", "chuteira", "chuteiras",
        "fut", "campo", "society",
    ],
    "tenis": [
        "tennis", "tênis", "tenis", "raquete", "raquetes", "quadra",
        "badminton", "padel",
    ],
    "basquete": [
        "basquete", "basketball", "basquetbol", "nba",
    ],
    "natacao": [
        "natação", "natacao", "swim", "swimming", "piscina",
        "nado", "nadar",
    ],
    "academia": [
        "academia", "gym", "musculação", "musculacao", "fitness",
        "treino", "training", "crossfit",
    ],
    "caminhada": [
        "caminhada", "walking", "walk", "trekking", "trilha",
        "hiking", "hike",
    ],
    "volei": [
        "vôlei", "volei", "volleyball", "voleibol",
    ],
    "vestuario": [
        "camiseta", "camisetas", "camisa", "camisas", "agasalho",
        "agasalhos", "jaqueta", "jaquetas", "moletom", "shorts",
        "bermuda", "bermudas", "conjunto", "conjuntos", "t-shirt",
        "shirt", "blusa", "blusas", "regata", "regatas", "calça",
        "calcas", "calças", "roupa", "roupas", "vestuário", "vestuario",
        "uniforme", "uniformes", "time", "times", "seleção", "selecao",
    ],
    "bolas": [
        "bola", "bolas", "bola de futebol", "bola de vôlei",
        "bola de volei", "bola de basquete", "bola de campo",
        "bola de society", "bola de salão", "bola de salao",
    ],
    "all-star": [
        "all star", "all-star", "allstar", "converse", "chuck taylor",
        "chuck",
    ],
    "acessorios": [
        "mochila", "mochilas", "boné", "bone", "bonés", "bones",
        "chinelo", "chinelos", "sandália", "sandalia", "sandálias",
        "sandalias", "luva", "luvas", "patins", "óculos", "oculos",
        "garrafa", "garrafas", "squeeze", "squeezes", "meião", "meiao",
        "acessório", "acessorio", "acessórios", "acessorios",
    ],
}

# Variações de escrita: quando um termo é reconhecido, os termos relacionados
# também entram na busca (ex.: "camiseta" também casa com "camisa").
KEYWORD_EXPANSIONS: dict[str, list[str]] = {
    "camiseta": ["camisa"],
    "camisetas": ["camisa"],
    "camisa": ["camiseta"],
    "camisas": ["camiseta"],
    "moletom": ["agasalho"],
    "jaqueta": ["agasalho"],
    "jaquetas": ["agasalho"],
    "time": ["camisa"],
    "times": ["camisa"],
    "seleção": ["camisa"],
    "selecao": ["camisa"],
}

# Termos que indicam busca por calçados numerados — o bot pode perguntar
# o número do pé do usuário.
FOOTWEAR_TERMS: set[str] = {
    "tênis", "tenis", "tennis", "chuteira", "chuteiras", "corrida",
    "running", "run", "runner", "correr", "jogging", "jog",
    "caminhada", "walking", "walk", "trekking", "trilha", "hiking",
    "hike", "society", "campo", "all star", "all-star", "allstar",
    "converse", "chuck taylor", "chuck", "shoe", "shoes", "sneaker",
    "sneakers", "cleat",
}

# Termos que indicam vestuário — gênero importa, número do pé não.
APPAREL_TERMS: set[str] = {
    "camiseta", "camisetas", "camisa", "camisas", "agasalho", "agasalhos",
    "jaqueta", "jaquetas", "moletom", "shorts", "bermuda", "bermudas",
    "conjunto", "conjuntos", "t-shirt", "shirt", "blusa", "blusas",
    "regata", "regatas", "calça", "calcas", "calças", "roupa", "roupas",
    "vestuário", "vestuario", "uniforme", "uniformes", "academia",
    "gym", "musculação", "musculacao", "fitness", "treino", "training",
    "crossfit", "time", "times", "seleção", "selecao",
}

# Termos neutros: produtos sem gênero e sem número (bolas, raquetes,
# acessórios) — não disparam perguntas pessoais.
NEUTRAL_TERMS: set[str] = {
    "bola", "bolas", "bola de futebol", "bola de vôlei", "bola de volei",
    "bola de basquete", "raquete", "raquetes", "corda", "cordas",
    "mochila", "mochilas", "boné", "bone", "bonés", "bones", "chinelo",
    "chinelos", "sandália", "sandalia", "sandálias", "sandalias",
    "luva", "luvas", "patins", "óculos", "oculos", "garrafa", "garrafas",
    "squeeze", "squeezes", "acessório", "acessorio", "acessórios",
    "acessorios", "grip", "overgrip", "meião", "meiao",
}

KNOWN_BRANDS: list[str] = [
    "nike", "adidas", "asics", "puma", "new balance", "newbalance",
    "mizuno", "under armour", "underarmour", "reebok", "fila",
    "columbia", "salomon", "brooks", "saucony", "hoka",
    "yonex", "wilson", "head", "babolat", "dunlop",
    "penalty", "topper", "umbro", "olympikus", "rainha",
    "diadora", "kappa", "lotto",
]

# Sinônimos de gênero/público-alvo (preferências pessoais do usuário)
GENDER_SYNONYMS: dict[str, list[str]] = {
    "masculino": ["masculino", "masculina", "masculinas", "homem", "homens", "para ele", "menino", "meninos", "men", "men's"],
    "feminino": ["feminino", "feminina", "femininas", "mulher", "mulheres", "para ela", "menina", "meninas", "women", "women's"],
    "infantil": ["infantil", "infantis", "criança", "crianca", "crianças", "criancas", "juvenil", "kids", "children"],
    "unissex": ["unissex", "unisex"],
}

# Menção explícita de tamanho: "tamanho 38", "número 40", "calço 42", "nº 38"
_SIZE_EXPLICIT_RE = re.compile(
    r"\b(?:tamanho|n[uú]mero|num\.?|cal[cç]o|nº)[\s:]*(?:de\s+)?(\d{1,2})\b",
    re.IGNORECASE,
)

# Número solto de dois dígitos (validado contra a faixa de calçados depois)
_SIZE_BARE_RE = re.compile(r"(?<![\d.])(\d{2})(?![\d.,])")

# Usuário dispensando a preferência: "tanto faz", "qualquer um"...
_SKIP_PREF_RE = re.compile(
    r"\b(?:tanto\s+faz|qualquer(?:\s+(?:um|uma|coisa|tamanho|n[uú]mero))?|indiferente|"
    r"n[aã]o\s+importa|n[aã]o\s+tem\s+prefer[eê]ncia|sem\s+prefer[eê]ncia)\b",
    re.IGNORECASE,
)

# Price patterns — EN and PT-BR
_PRICE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # "under 500", "below 500", "até 500", "max 500", "máximo 500"
    (re.compile(
        r"(?:under|below|abaixo\s+de|até|ate|max(?:imo)?|máximo)\s*R?\$?\s*(\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    ), "max"),
    # "above 200", "acima de 200", "min 200", "mínimo 200", "from 200"
    (re.compile(
        r"(?:above|over|acima\s+de|min(?:imo)?|mínimo|from|a\s+partir\s+de)\s*R?\$?\s*(\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    ), "min"),
    # "between 200 and 500" / "entre 200 e 500"
    (re.compile(
        r"(?:between|entre)\s*R?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:and|e|a)\s*R?\$?\s*(\d+(?:[.,]\d+)?)",
        re.IGNORECASE,
    ), "range"),
]

_AVAILABLE_PATTERNS = re.compile(
    r"\b(?:in\s+stock|disponível|disponivel|available|tem\s+estoque|com\s+estoque|em\s+estoque|tem)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ParsedIntent:
    category_keywords: list[str] = field(default_factory=list)
    # Raw terms matched from the message (e.g. "chuteira", "corrida") — used
    # alongside the mapped category slugs so name/slug searches also hit.
    keywords: list[str] = field(default_factory=list)
    brand: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    available: bool | None = None
    # Preferências pessoais do usuário (persistem por sessão no chat)
    gender: str | None = None
    size: int | None = None
    skip_preferences: bool = False
    raw_query: str = ""

    def has_filters(self) -> bool:
        return bool(
            self.category_keywords or self.brand
            or self.price_min is not None or self.price_max is not None
            or self.available is not None
        )

    @property
    def is_footwear_search(self) -> bool:
        """Busca por calçados numerados (tênis, chuteiras...): vale perguntar
        o número. Buscas com termos neutros (bola, raquete...) não contam."""
        terms = set(self.keywords)
        if terms & NEUTRAL_TERMS:
            return False
        return bool(terms & FOOTWEAR_TERMS)

    @property
    def is_gendered_search(self) -> bool:
        """Busca por produtos com versões de gênero (calçados e vestuário):
        vale perguntar para quem é."""
        terms = set(self.keywords)
        if terms & NEUTRAL_TERMS:
            return False
        return bool(terms & (FOOTWEAR_TERMS | APPAREL_TERMS))


def _extract_size(norm: str, has_product_context: bool) -> int | None:
    """Extrai um número de calçado (16–50) da mensagem normalizada.

    Com contexto de produto (categoria ou gênero citado), um número solto
    como "38" também vale como tamanho. Menções de preço ("até 500") são
    mascaradas para não serem confundidas com tamanho.
    """
    m = _SIZE_EXPLICIT_RE.search(norm)
    if m:
        size = int(m.group(1))
        return size if 16 <= size <= 50 else None

    if not has_product_context:
        return None

    # Mascara menções de preço para não ler "até 500" como tamanho
    masked = norm
    for pattern, _ in _PRICE_PATTERNS:
        masked = pattern.sub(lambda mm: " " * len(mm.group(0)), masked)

    for bare in _SIZE_BARE_RE.finditer(masked):
        size = int(bare.group(1))
        return size if 16 <= size <= 50 else None
    return None


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def _normalise(text: str) -> str:
    """Lower-case, collapse whitespace."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _parse_price(raw: str) -> float:
    """Convert '1.200,50' or '1200.50' → float."""
    clean = raw.replace(".", "").replace(",", ".")
    return float(clean)


def parse_intent(message: str) -> ParsedIntent:
    """
    Parse a user message and extract structured search filters.

    Args:
        message: Free-form user query in English or Portuguese.

    Returns:
        ParsedIntent dataclass with extracted filters.
    """
    norm = _normalise(message)
    intent = ParsedIntent(raw_query=message)

    # --- Brand detection (longest match first to prefer "new balance") -----
    for brand in sorted(KNOWN_BRANDS, key=len, reverse=True):
        if brand in norm:
            intent.brand = brand.title()
            break

    # --- Category detection ------------------------------------------------
    matched_categories: set[str] = set()
    matched_keywords: set[str] = set()
    for cat_slug, keywords in CATEGORY_SYNONYMS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", norm):
                matched_categories.add(cat_slug)
                matched_keywords.add(kw)
                break
    intent.category_keywords = list(matched_categories)

    # Termos expandidos entram junto (ex.: "camiseta" também busca "camisa")
    for kw in list(matched_keywords):
        matched_keywords.update(KEYWORD_EXPANSIONS.get(kw, []))
    intent.keywords = sorted(matched_keywords)

    # --- Price extraction --------------------------------------------------
    for pattern, kind in _PRICE_PATTERNS:
        match = pattern.search(norm)
        if match:
            if kind == "range":
                intent.price_min = _parse_price(match.group(1))
                intent.price_max = _parse_price(match.group(2))
            elif kind == "max":
                intent.price_max = _parse_price(match.group(1))
            elif kind == "min":
                intent.price_min = _parse_price(match.group(1))
            break  # first match wins

    # --- Availability ------------------------------------------------------
    if _AVAILABLE_PATTERNS.search(norm):
        intent.available = True

    # --- Preferências pessoais (gênero e número do calçado) -----------------
    for gender, synonyms in GENDER_SYNONYMS.items():
        for syn in synonyms:
            if re.search(r"\b" + re.escape(syn) + r"\b", norm):
                intent.gender = gender
                break

    intent.size = _extract_size(norm, bool(intent.category_keywords or intent.gender))

    if _SKIP_PREF_RE.search(norm):
        intent.skip_preferences = True

    return intent
