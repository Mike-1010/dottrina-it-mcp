"""Funzioni pure di parsing e di confronto testuale (nessun accesso alla rete).

I parser cercano i collegamenti per forma dell'URL (non per classi CSS): reggono meglio
i cambi di grafica dei siti. Ogni elemento restituito è un dict con le chiavi:
fonte, tipo, titolo, autori, data (AAAA-MM-GG o None), url.
"""
from __future__ import annotations

import html as htmllib
import re
import unicodedata
from datetime import date
from urllib.parse import unquote, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

# ------------------------------------------------------------------ testo e date
MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6,
    "luglio": 7, "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
    "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}
_RE_DATE_TXT = re.compile(r"\b(\d{1,2})\s+([A-Za-zÀ-ÿ]+)\s+((?:19|20)\d{2})\b")
_RE_DATE_NUM = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.]((?:19|20)\d{2})\b")

STOPWORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di", "a", "da", "in", "con",
    "su", "per", "tra", "fra", "e", "ed", "o", "od", "del", "dello", "della", "dei", "degli",
    "delle", "al", "allo", "alla", "ai", "agli", "alle", "dal", "dallo", "dalla", "dai",
    "dagli", "dalle", "nel", "nello", "nella", "nei", "negli", "nelle", "sul", "sullo",
    "sulla", "sui", "sugli", "sulle", "che", "non", "si", "come", "art", "artt", "n", "nn",
    "c", "cc", "p", "pp", "cpc", "cpp", "cp", "cost", "sez", "sezione", "sentenza", "sent",
    "ord", "ordinanza", "nota", "the", "of", "and",
}


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(s or "")).strip()


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def stem(tok: str) -> str:
    if tok.isdigit() or len(tok) <= 4:
        return tok
    return re.sub(r"(zioni|zione|mente|ità|ita|i|e|a|o)$", "", tok) or tok


def tokens(query: str) -> list[str]:
    out = []
    for t in norm(query).split():
        if t in STOPWORDS:
            continue
        out.append(stem(t))
    return list(dict.fromkeys(out))


def parse_date(text: str | None) -> str | None:
    """Prima data trovata nel testo, in formato ISO."""
    if not text:
        return None
    m = _RE_DATE_TXT.search(text)
    if m and m.group(2).lower() in MESI:
        try:
            return date(int(m.group(3)), MESI[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            pass
    m = _RE_DATE_NUM.search(text)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            pass
    return None


_RE_LABEL_DATE = re.compile(
    r"(?:pubblicat[oa]|data di pubblicazione|creat[oa]|pubblicazione)\s*(?:il|:)?\s*:?\s*"
    r"(\d{1,2}(?:\s+[A-Za-zÀ-ÿ]+\s+|[/.]\d{1,2}[/.])(?:19|20)\d{2})", re.I)
_RE_FASCICOLO = re.compile(r"fascicolo\s*n[°º.]?\s*(\d{1,2}\s*/\s*(?:19|20)\d{2})", re.I)


def parse_labeled_date(text: str | None) -> str | None:
    """Data preceduta da un'etichetta di pubblicazione ('Pubblicato:', 'Data di pubblicazione')."""
    m = _RE_LABEL_DATE.search(text or "")
    return parse_date(m.group(1)) if m else None


def parse_fascicolo(text: str | None) -> str | None:
    m = _RE_FASCICOLO.search(text or "")
    return re.sub(r"\s+", "", m.group(1)) if m else None


def clean_author(name: str) -> str:
    return clean(re.sub(r"^(a cura di|di)\s+", "", clean(name), flags=re.I))


def clean_title(title: str | None) -> str | None:
    """Toglie dal titolo della pagina il nome della rivista e, per Sistema Penale, l'autore."""
    if not title:
        return title
    t = re.sub(r"\s*[|\-–]\s*(Sistema Penale(\s*\|\s*SP)?|Archivio Penale|Questione Giustizia|"
               r"Judicium|Rivista AIC|Persona e Mercato)\s*$", "", clean(title), flags=re.I)
    t = re.sub(r"\s*\|\s*SP\s*$", "", t)
    t = re.sub(r"^[A-Z]\.(\s*[A-Z]\.)*\s*[A-Za-zÀ-ÿ'’ ]{2,40}\s*\|\s*", "", t)  # "F. Lazzarini | ..."
    return t


def humanize_slug(url: str) -> str:
    slug = unquote(urlparse(url).path.rstrip("/").split("/")[-1])
    return clean(slug.replace("-", " ")).capitalize()


# ------------------------------------------------------------------ helper HTML
def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html or "", "html.parser")


def _container(a: Tag, pattern: re.Pattern, max_up: int = 5) -> Tag:
    """Risale dal link al contenitore più ampio che contiene UN solo elemento dell'elenco."""
    best = a
    node = a
    for _ in range(max_up):
        parent = node.parent
        if parent is None or parent.name in ("body", "html", "[document]"):
            break
        hrefs = {x.get("href", "").split("?")[0].split("#")[0]
                 for x in parent.find_all("a", href=True) if pattern.search(x.get("href", ""))}
        if len(hrefs) > 1:
            break
        best = node = parent
    return best


def _date_in_siblings(box: Tag, pattern: re.Pattern, max_sib: int = 4) -> str | None:
    """Data negli elementi che seguono il contenitore (es. <dt> titolo + <dd> data in Joomla)."""
    for i, sib in enumerate(box.find_next_siblings()):
        if i >= max_sib:
            break
        if any(pattern.search(x.get("href", "")) for x in sib.find_all("a", href=True)):
            break
        d = parse_date(clean(sib.get_text(" ")))
        if d:
            return d
    return None


def _anchor_title(a: Tag) -> str:
    t = clean(a.get_text(" "))
    if not t or t.startswith("/") or t.startswith("http"):
        t = clean(a.get("title", ""))
    return t


def _collect(html: str, base: str, pattern: re.Pattern, fonte: str,
             tipo_fn, author_pattern: re.Pattern | None = None) -> list[dict]:
    """Raccoglie gli elementi di un elenco: un elemento per URL, con il titolo più lungo."""
    soup = _soup(html)
    items: dict[str, dict] = {}
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not pattern.search(href):
            continue
        url = urljoin(base + "/", href).split("#")[0]
        if "?out=print" in url:
            continue
        title = _anchor_title(a)
        box = _container(a, pattern)
        box_text = clean(box.get_text(" "))
        autori = []
        if author_pattern is not None:
            for x in box.find_all("a", href=True):
                if author_pattern.search(x["href"]):
                    n = clean_author(x.get_text(" "))
                    if n and n.lower() not in ("di", "a cura di") and n not in autori:
                        autori.append(n)
        it = items.get(url)
        if it is None:
            it = items[url] = {"fonte": fonte, "tipo": tipo_fn(url), "titolo": "",
                               "autori": [], "data": None, "url": url}
        if len(title) > len(it["titolo"]):
            it["titolo"] = title
        for n in autori:
            if n not in it["autori"]:
                it["autori"].append(n)
        if not it["data"]:
            # la data va cercata fuori dal titolo (i titoli citano spesso date di decisioni o
            # leggi); ordine: data con etichetta, data numerica gg/mm/aaaa, data in lettere
            rest = box_text
            for t in sorted({title, it["titolo"]}, key=len, reverse=True):
                if len(t) > 15:
                    rest = rest.replace(t, " ")
            m = _RE_DATE_NUM.search(rest)
            it["data"] = (parse_labeled_date(rest) or (parse_date(m.group(0)) if m else None)
                          or parse_date(rest) or _date_in_siblings(box, pattern))
    out = []
    for it in items.values():
        if not it["titolo"]:
            it["titolo"] = humanize_slug(it["url"])
        out.append(it)
    return out


# ------------------------------------------------------------------ Sistema Penale
SP_BASE = "https://www.sistemapenale.it"
SP_TIPI = ("articolo", "scheda", "notizie", "documenti", "opinioni", "sentenza", "recensione")
_SP_ITEM = re.compile(r"/it/(" + "|".join(SP_TIPI) + r")/[^/?#]+")
_SP_AUTH = re.compile(r"/it/autori-di-sp/[^/?#]+")


def sp_tipo(url: str) -> str:
    m = _SP_ITEM.search(url)
    return {"notizie": "notizia", "documenti": "documento", "opinioni": "opinione"}.get(
        m.group(1), m.group(1)) if m else "contributo"


def parse_sitemap_locs(xml: str) -> list[str]:
    return [clean(u) for u in re.findall(r"<loc>\s*([^<]+?)\s*</loc>", xml or "")]


def sp_items_from_sitemap(xml: str) -> list[dict]:
    out = []
    for u in parse_sitemap_locs(xml):
        if _SP_ITEM.search(u):
            out.append({"fonte": "sistemapenale", "tipo": sp_tipo(u), "titolo": humanize_slug(u),
                        "autori": [], "data": None, "url": u, "dal_sitemap": True})
    return out


def sp_parse_list(html: str) -> list[dict]:
    return _collect(html, SP_BASE, _SP_ITEM, "sistemapenale", sp_tipo, _SP_AUTH)


# ------------------------------------------------------------------ Questione Giustizia
QG_BASE = "https://www.questionegiustizia.it"
_QG_ITEM = re.compile(r"/articolo/[^/?#]+")
_QG_AUTH = re.compile(r"/autore/[^/?#]+")


def qg_parse_list(html: str) -> list[dict]:
    return _collect(html, QG_BASE, _QG_ITEM, "questionegiustizia", lambda u: "articolo", _QG_AUTH)


# ------------------------------------------------------------------ Archivio Penale
AP_BASE = "https://archiviopenale.it"
_AP_FASC = re.compile(r"/fascicoli/\d+")
_AP_ART = re.compile(r"/articoli/\d+")
_AP_CONT = re.compile(r"/contenuti/\d+")


def ap_parse_fascicoli(html: str) -> list[dict]:
    """Fascicoli della rivista web, nell'ordine della pagina (dal più recente)."""
    out, seen = [], set()
    for a in _soup(html).find_all("a", href=True):
        if not _AP_FASC.search(a["href"]):
            continue
        url = urljoin(AP_BASE + "/", a["href"])
        title = _anchor_title(a)
        if url in seen or "web" not in (title + url).lower():
            continue
        seen.add(url)
        out.append({"titolo": title or humanize_slug(url), "url": url})
    return out


def ap_parse_articles(html: str, fascicolo: str | None = None) -> list[dict]:
    items = _collect(html, AP_BASE, _AP_ART, "archiviopenale", lambda u: "articolo")
    soup = _soup(html)
    # autore: nelle pagine dei fascicoli il nome segue/precede il titolo nel contenitore
    for it in items:
        if fascicolo:
            it["fascicolo"] = fascicolo
        a = soup.find("a", href=lambda h: h and urljoin(AP_BASE + "/", h).split("#")[0] == it["url"])
        if a is None:
            continue
        box_text = clean(_container(a, _AP_ART).get_text(" | "))
        rest = box_text.replace(it["titolo"], " | ")
        parts = [p.strip(" |-") for p in rest.split("|")]
        cand = [p for p in parts if 2 <= len(p.split()) <= 6 and not parse_date(p)
                and not re.search(r"(pubblicat|open access|leggi|scarica|fascicolo)", p, re.I)]
        if cand and not it["autori"]:
            it["autori"] = [cand[0]]
    return items


def ap_parse_contenuti(html: str, sezione: str | None = None) -> list[dict]:
    items = _collect(html, AP_BASE, _AP_CONT, "archiviopenale", lambda u: "nota/documento")
    for it in items:
        if sezione:
            it["sezione"] = sezione
        # la data nel titolo è quella della decisione, non della pubblicazione
        d = parse_date(it["titolo"])
        if d:
            it["data_decisione"] = d
            if it["data"] == d:
                it["data"] = None
    return items


def ap_access(html: str) -> dict:
    """Stato di accesso di una pagina di Archivio Penale."""
    text = clean(_soup(html).get_text(" ")).lower()
    links = [a["href"] for a in _soup(html).find_all("a", href=True)]
    free = [urljoin(AP_BASE + "/", h) for h in links
            if re.search(r"/file/download(articolo)?\?", h, re.I) and "pagamento" not in h.lower()]
    paid = [h for h in links if "pagamento" in h.lower()]
    return {"open_access": "open access" in text, "download": free[0] if free else None,
            "a_pagamento": bool(paid)}


# ------------------------------------------------------------------ Rivista AIC
AIC_BASE = "https://www.rivistaaic.it"
_AIC_ITEM = re.compile(r"/it/rivista/ultimi-contributi-pubblicati/[^/?#]+/[^/?#]+")
_AIC_AUTH = re.compile(r"/it/rivista/ultimi-contributi-pubblicati/[^/?#]+/?$")


def aic_parse_list(html: str) -> list[dict]:
    items = _collect(html, AIC_BASE, _AIC_ITEM, "rivistaaic", lambda u: "contributo")
    soup = _soup(html)
    for it in items:
        # nei risultati di Rivista AIC il testo vicino al titolo è un estratto dell'abstract:
        # si accetta solo una data con etichetta ("Creato:", "Pubblicato:")
        it["data"] = None
        a = soup.find("a", href=lambda h: h and urljoin(AIC_BASE + "/", h).split("#")[0] == it["url"])
        if a is not None:
            box = _container(a, _AIC_ITEM)
            texts = [clean(box.get_text(" "))] + [clean(s.get_text(" ")) for s in box.find_next_siblings()[:4]]
            for t in texts:
                d = parse_labeled_date(t)
                if d:
                    it["data"] = d
                    break
        if not it["autori"]:
            seg = unquote(urlparse(it["url"]).path.rstrip("/").split("/")[-2])
            it["autori"] = [clean(seg.replace("-", " ")).title()]
    return items


def aic_pdf_link(html: str) -> str | None:
    for a in _soup(html).find_all("a", href=True):
        if re.search(r"/images/rivista/pdf/.+\.pdf$", a["href"], re.I):
            return urljoin(AIC_BASE + "/", a["href"])
    return None


# ------------------------------------------------------------------ Judicium (REST)
JUD_BASE = "https://www.judicium.it"


def jud_items(posts: list[dict], cat_names: dict[int, str] | None = None) -> list[dict]:
    out = []
    for p in posts or []:
        cats = p.get("categories") or []
        tipo = "aggiornamento"
        if cat_names:
            extra = [cat_names[c] for c in cats if c in cat_names and c != 60]
            if extra:
                tipo = "aggiornamento - " + ", ".join(extra)
        out.append({"fonte": "judicium", "tipo": tipo,
                    "titolo": clean(BeautifulSoup((p.get("title") or {}).get("rendered", ""),
                                                  "html.parser").get_text(" ")),
                    "autori": [], "data": (p.get("date") or "")[:10] or None,
                    "url": p.get("link"), "accesso_libero": 60 in cats})
    return out


# ------------------------------------------------------------------ Persona e Mercato
PEM_BASE = "https://www.personaemercato.it"


def pem_items_from_issue(post: dict) -> list[dict]:
    """Contributi elencati nel post di un numero: <strong>Sezione</strong> + <li><a>AUTORE, Titolo</a>."""
    title = clean(BeautifulSoup((post.get("title") or {}).get("rendered", ""), "html.parser").get_text(" "))
    numero = re.sub(r"(?i)persona e mercato,?\s*", "", title).strip() or title
    soup = _soup((post.get("content") or {}).get("rendered", ""))
    out, sezione = [], None
    for el in soup.find_all(["strong", "li"]):
        if el.name == "strong":
            sezione = clean(el.get_text(" ")) or sezione
            continue
        a = el.find("a", href=True)
        if not a or not a["href"].lower().endswith(".pdf"):
            continue
        txt = clean(a.get_text(" "))
        autori, titolo = [], txt
        m = re.match(r"^([A-ZÀ-Ý][A-ZÀ-Ý.'’\s\-]+(?:\s*(?:e|,)\s*[A-ZÀ-Ý.'’\s\-]+)*),\s*(.+)$", txt)
        if m:
            autori = [clean(x).title() for x in re.split(r"\s+e\s+|,\s*", m.group(1)) if clean(x)]
            titolo = m.group(2)
        url = a["href"].replace("http://", "https://", 1)
        out.append({"fonte": "personaemercato", "tipo": (sezione or "contributo").lower(),
                    "titolo": titolo, "autori": autori, "data": (post.get("date") or "")[:10] or None,
                    "url": url, "fascicolo": numero})
    return out


# ------------------------------------------------------------------ ricerca e ranking
def score(item: dict, toks: list[str]) -> float:
    if not toks:
        return 0.0
    hay = " ".join([item.get("titolo", ""), " ".join(item.get("autori", [])),
                    unquote(urlparse(item.get("url", "")).path).replace("-", " "),
                    item.get("fascicolo", "") or "", item.get("sezione", "") or ""])
    words = set()
    for w in norm(hay).split():
        words.add(w)
        words.add(stem(w))
    # corrispondenza: parola uguale, prefisso (>= 5 lettere) o parola composta che la contiene
    # (>= 6 lettere: "riciclaggio" trova "antiriciclaggio")
    hit = sum(1 for t in toks if t in words
              or (len(t) >= 5 and any(w.startswith(t) for w in words))
              or (len(t) >= 6 and any(t in w for w in words)))
    return hit / len(toks)


def rank(items: list[dict], query: str, autore: str | None = None, anno: int | None = None,
         soglia: float | None = None) -> list[dict]:
    toks = tokens(query) if query else []
    out = []
    for it in items:
        if anno and not (it.get("data") or "").startswith(str(anno)):
            continue
        if autore:
            a_toks = tokens(autore)
            hay = norm(" ".join(it.get("autori", [])) + " " + it.get("url", "").replace("-", " "))
            if not all(t in hay for t in a_toks):
                continue
        s = score(it, toks) if toks else 1.0
        need = soglia if soglia is not None else (1.0 if len(toks) <= 2 else 0.6)
        if it.get("_live"):
            need = 0.0  # risultati della ricerca interna del sito: la pertinenza l'ha già valutata il sito
        if s >= need:
            out.append({**it, "_score": round(s, 2)})
    out.sort(key=lambda x: (x["_score"], x.get("data") or ""), reverse=True)
    return out


def dedupe(items: list[dict]) -> list[dict]:
    """Un elemento per URL; preferisce quello con più metadati (non da sitemap)."""
    best: dict[str, dict] = {}
    for it in items:
        k = (it.get("url") or "").rstrip("/")
        cur = best.get(k)
        if cur is None or (cur.get("dal_sitemap") and not it.get("dal_sitemap")):
            best[k] = dict(it)
    return list(best.values())


# ------------------------------------------------------------------ estremi di una decisione
_ORGANI = [
    (r"sez(ioni)?\.?\s*un(ite)?|ss\.?\s*uu|s\.?u\.", "Sezioni Unite"),
    (r"cass(azione)?", "Cassazione"),
    (r"corte\s+cost(ituzionale)?|c\.\s*cost|consulta", "Corte costituzionale"),
    (r"cgue|corte\s+di\s+giustizia", "Corte di giustizia UE"),
    (r"cedu|corte\s+edu|strasburgo", "Corte EDU"),
    (r"cons(iglio)?\s+(di\s+)?stato", "Consiglio di Stato"),
]


def parse_estremi(estremi: str) -> dict:
    s = estremi or ""
    numero = anno = None
    m = re.search(r"\b(\d{1,6})\s*/\s*((?:19|20)\d{2})\b", s)
    if m:
        numero, anno = m.group(1), m.group(2)
    else:
        m = re.search(r"\bn(?:\.|um(?:ero)?)?\s*(\d{1,6})\b", s, re.I)
        if m:
            numero = m.group(1)
        y = re.findall(r"\b((?:19|20)\d{2})\b", s)
        if y:
            anno = y[-1]
    organo = None
    for pat, name in _ORGANI:
        if re.search(pat, s, re.I):
            organo = name
            break
    return {"numero": numero, "anno": anno, "organo": organo, "data": parse_date(s), "testo": s}


def match_decisione(item: dict, est: dict) -> str | None:
    """'forte' se titolo/URL citano numero e anno; 'possibile' se solo il numero o organo+data."""
    hay = norm(" ".join([item.get("titolo", ""), unquote(item.get("url", "")).replace("-", " ")]))
    words = set(hay.split())
    num, anno = est.get("numero"), est.get("anno")
    if num and num in words:
        if anno and anno in words:
            return "forte"
        if len(num) >= 4:
            return "possibile"
    if est.get("data") and est.get("organo"):
        y, mth, d = est["data"].split("-")
        mese = [k for k, v in MESI.items() if v == int(mth)][0]
        if str(int(d)) in words and mese in words and y in words:
            return "possibile"
    return None
