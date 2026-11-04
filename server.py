"""dottrina-it-mcp - connettore MCP per la dottrina italiana ad accesso libero.

Fonti (livello A, lettura su richiesta consentita): Sistema Penale, Questione Giustizia,
Archivio Penale (solo contributi web 'open access'), Judicium (solo 'Aggiornamenti'),
Persona e Mercato, Rivista AIC. Le fonti di livello B e C sono solo segnalate.

Avvio locale:   python server.py --probe "interrogatorio preventivo"
                python server.py --leggi https://www.sistemapenale.it/it/articolo/...
Server MCP:     python server.py   (streamable HTTP su $PORT, percorso $MCP_PATH)
                MCP_TRANSPORT=stdio python server.py
"""
from __future__ import annotations

import argparse
import asyncio
import io
import json
import os
import re
import time
from collections import OrderedDict
from urllib import robotparser
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP

import config
import parsers as P

try:  # estrazione del testo principale; se manca si usa BeautifulSoup
    import trafilatura
except ImportError:  # pragma: no cover
    trafilatura = None

INSTRUCTIONS = (
    "Ricerca e lettura di dottrina giuridica italiana AD ACCESSO LIBERO: saggi, note a "
    "sentenza, commenti a caldo e rassegne da Sistema Penale, Questione Giustizia, Archivio "
    "Penale (solo contributi web open access), Judicium (solo 'Aggiornamenti'), Persona e "
    "Mercato e Rivista AIC. Flusso: `cerca_dottrina` (tema, autore, anno, fonti) oppure "
    "`commenti_a_sentenza` (estremi di una decisione); poi `leggi_contributo` sull'URL, a "
    "blocchi con `da_carattere`. `ultime_pubblicazioni` per le novità, `elenca_fonti` per "
    "copertura e limiti. Cita sempre autore, titolo, rivista, data e URL; riassumi con parole "
    "tue e non riprodurre lunghi passi (licenze NC-ND e L. 633/1941). Le fonti di livello B e "
    "C (Federalismi, Consulta Online, Jus Civile, Archivio DPC, DoGi...) non vengono lette: "
    "segnala il link all'utente. Per norme e giurisprudenza usa prima i connettori dedicati "
    "(mcp-legal-it, ilcaso.it)."
)

mcp = FastMCP(
    "dottrina-it",
    instructions=INSTRUCTIONS,
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "8000")),
    # Consiglio: imposta MCP_PATH a un percorso segreto, es. /k3j9x-mcp
    streamable_http_path=os.getenv("MCP_PATH", "/mcp"),
)

# ---------------------------------------------------------------- HTTP layer
_client = httpx.AsyncClient(
    headers={"User-Agent": config.USER_AGENT, "Accept-Language": "it-IT,it;q=0.9"},
    timeout=config.TIMEOUT,
    follow_redirects=True,
)
_cache: "OrderedDict[str, tuple[float, object]]" = OrderedDict()
_locks: dict[str, asyncio.Lock] = {}
_last: dict[str, float] = {}
_robots: dict[str, robotparser.RobotFileParser] = {}


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


SOURCE_HOSTS = {_host(s["base"]): sid for sid, s in config.SOURCES.items()}
OTHER_HOSTS = {_host(o["url"]): o for o in config.OTHER_SOURCES}


def _err(e: BaseException) -> str:
    return f"{type(e).__name__}: {e}".rstrip(": ")


def _cache_get(key: str, ttl: float = config.CACHE_TTL):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < ttl:
        return hit[1]
    return None


def _cache_put(key: str, val: object) -> None:
    _cache[key] = (time.monotonic(), val)
    _cache.move_to_end(key)
    while len(_cache) > config.CACHE_MAX:
        _cache.popitem(last=False)


async def _robots_for(url: str) -> robotparser.RobotFileParser:
    host = _host(url)
    rp = _robots.get(host)
    if rp is not None:
        return rp
    p = urlparse(url)
    rp = robotparser.RobotFileParser()
    try:
        r = await _client.get(f"{p.scheme}://{p.netloc}/robots.txt")
        if r.status_code in (401, 403):
            rp.disallow_all = True
        elif r.status_code == 200 and "text/html" not in r.headers.get("content-type", ""):
            rp.parse(r.text.splitlines())
        else:
            rp.parse([])
    except httpx.HTTPError:
        rp.parse([])
    _robots[host] = rp
    return rp


async def _get(url: str, params: dict | None = None) -> httpx.Response:
    """GET verso una fonte di livello A, con robots.txt e intervallo minimo per sito."""
    host = _host(url)
    if host not in SOURCE_HOSTS:
        raise PermissionError(f"{host} non è una fonte di livello A di questo connettore")
    rp = await _robots_for(url)
    if not rp.can_fetch(config.USER_AGENT, url):
        raise PermissionError(f"robots.txt del sito non consente l'accesso a {url}")
    delay = max(config.MIN_INTERVAL, float(rp.crawl_delay(config.USER_AGENT) or 0))
    lock = _locks.setdefault(host, asyncio.Lock())
    async with lock:
        wait = delay - (time.monotonic() - _last.get(host, 0.0))
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            r = await _client.get(url, params=params)
        finally:
            _last[host] = time.monotonic()
    r.raise_for_status()
    return r


async def fetch_text(url: str, params: dict | None = None) -> str:
    key = "t:" + url + json.dumps(params or {}, sort_keys=True)
    hit = _cache_get(key)
    if hit is not None:
        return hit  # type: ignore[return-value]
    text = (await _get(url, params)).text
    _cache_put(key, text)
    return text


async def fetch_json(url: str, params: dict | None = None):
    key = "j:" + url + json.dumps(params or {}, sort_keys=True)
    hit = _cache_get(key)
    if hit is not None:
        return hit
    r = await _get(url, params)
    data = r.json()
    _cache_put(key, (data, dict(r.headers)))
    return data, dict(r.headers)


async def fetch_doc(url: str) -> tuple[str, str]:
    """Scarica un documento; restituisce (tipo, testo) con tipo 'pdf' o 'html'."""
    key = "d:" + url
    hit = _cache_get(key)
    if hit is not None:
        return hit  # type: ignore[return-value]
    r = await _get(url)
    if len(r.content) > config.PDF_MAX_BYTES:
        raise ValueError("documento troppo grande")
    ctype = r.headers.get("content-type", "").lower()
    if "pdf" in ctype or r.content[:5] == b"%PDF-":
        res = ("pdf", pdf_text(r.content))
    else:
        res = ("html", r.text)
    _cache_put(key, res)
    return res


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = []
    for i, page in enumerate(reader.pages):
        if i >= config.PDF_MAX_PAGES:
            parts.append("[... pagine successive non estratte ...]")
            break
        parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def html_main(html: str, url: str | None = None) -> dict:
    """Testo principale e metadati di una pagina HTML."""
    meta = {"titolo": None, "autori": [], "data": None}
    text = None
    if trafilatura is not None:
        try:
            text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True,
                                       favor_recall=True)
            md = trafilatura.extract_metadata(html, default_url=url)
            if md is not None:
                meta["titolo"] = md.title
                if md.author:
                    meta["autori"] = [a.strip() for a in re.split(r";|\|", md.author) if a.strip()]
                meta["data"] = md.date
        except Exception:  # noqa: BLE001 - qualunque errore: si ripiega su BeautifulSoup
            text = None
    if not text:
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "nav", "header", "footer", "form", "noscript"]):
            t.decompose()
        root = soup.find("article") or soup.find("main") or soup.body or soup
        text = re.sub(r"\n{3,}", "\n\n", root.get_text("\n")).strip()
        if not meta["titolo"] and soup.title:
            meta["titolo"] = P.clean(soup.title.get_text())
    return {**meta, "testo": text or ""}


def _slice(text: str, da: int, maxc: int) -> dict:
    da = max(0, int(da or 0))
    maxc = max(500, min(int(maxc or config.MAX_CARATTERI_DEFAULT), 30000))
    chunk = text[da:da + maxc]
    nxt = da + len(chunk)
    return {"testo": chunk, "da_carattere": da, "lunghezza_totale": len(text),
            "prossimo_da_carattere": nxt if nxt < len(text) else None}


# ---------------------------------------------------------------- indici in memoria
class Index:
    def __init__(self, sid: str):
        self.sid = sid
        self.items: list[dict] = []
        self.built_at = 0.0
        self.task: asyncio.Task | None = None
        self.error: str | None = None
        self.pages_ok = 0
        self.pages_ko = 0

    @property
    def ready(self) -> bool:
        return self.built_at > 0

    @property
    def stale(self) -> bool:
        return time.monotonic() - self.built_at > config.INDEX_TTL


INDEXED = ("sistemapenale", "questionegiustizia", "archiviopenale", "personaemercato")
LIVE = ("judicium", "rivistaaic")
_indexes = {sid: Index(sid) for sid in INDEXED}


async def _pages(ix: Index, urls: list[str], parser, **kw) -> list[dict]:
    out = []
    for u in urls:
        try:
            out += parser(await fetch_text(u), **kw)
            ix.pages_ok += 1
        except (httpx.HTTPError, PermissionError, ValueError) as e:
            ix.pages_ko += 1
            ix.error = _err(e)
    return out


async def _build_sistemapenale(ix: Index) -> list[dict]:
    base = config.SOURCES["sistemapenale"]["base"]
    items: list[dict] = []
    urls = [f"{base}/it/contributi"] + [f"{base}/it/contributi?page={n}"
                                         for n in range(2, config.SP_LIST_PAGES + 1)]
    items += await _pages(ix, urls, P.sp_parse_list)
    try:
        items += P.sp_items_from_sitemap(await fetch_text(f"{base}/sitemap.xml"))
        ix.pages_ok += 1
    except (httpx.HTTPError, PermissionError) as e:
        ix.pages_ko += 1
        ix.error = _err(e)
    return items


async def _build_questionegiustizia(ix: Index) -> list[dict]:
    base = config.SOURCES["questionegiustizia"]["base"]
    items: list[dict] = []
    for cat in config.QG_CATEGORIES:
        for n in range(1, config.QG_PAGES + 1):
            url = f"{base}/cat/{cat}" + (f"?page={n}" if n > 1 else "")
            try:
                items += P.qg_parse_list(await fetch_text(url))
                ix.pages_ok += 1
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404 and n > 1:
                    break  # la categoria ha meno pagine: non è un errore
                ix.pages_ko += 1
                ix.error = _err(e)
                break
            except (httpx.HTTPError, PermissionError) as e:
                ix.pages_ko += 1
                ix.error = _err(e)
                break
    return items


async def _build_archiviopenale(ix: Index) -> list[dict]:
    base = config.SOURCES["archiviopenale"]["base"]
    items: list[dict] = []
    try:
        fasc = P.ap_parse_fascicoli(await fetch_text(f"{base}/rivista-web/rivista/3"))
        ix.pages_ok += 1
    except (httpx.HTTPError, PermissionError) as e:
        fasc, ix.error = [], _err(e)
        ix.pages_ko += 1
    for f in fasc[: config.AP_FASCICOLI]:
        items += await _pages(ix, [f["url"]], P.ap_parse_articles, fascicolo=f["titolo"])
    for slug, sid in config.AP_SECTIONS.items():
        urls = [f"{base}/{slug}/sezioni/{sid}"] + [f"{base}/{slug}/sezioni/{sid}?p={n}"
                                                    for n in range(2, config.AP_SECTION_PAGES + 1)]
        items += await _pages(ix, urls, P.ap_parse_contenuti, sezione=slug.replace("-", " "))
    return items


async def _build_personaemercato(ix: Index) -> list[dict]:
    base = config.SOURCES["personaemercato"]["base"]
    items: list[dict] = []
    for page in range(1, 6):
        try:
            data, headers = await fetch_json(
                f"{base}/wp-json/wp/v2/posts",
                {"categories": config.PEM_ISSUE_CATEGORY, "per_page": 100, "page": page,
                 "_fields": "title,link,date,content"})
            ix.pages_ok += 1
        except (httpx.HTTPError, PermissionError, ValueError) as e:
            if page == 1:
                ix.pages_ko += 1
                ix.error = _err(e)
            break
        for post in data or []:
            items += P.pem_items_from_issue(post)
        if page >= int(headers.get("x-wp-totalpages", "1") or 1):
            break
    return items


BUILDERS = {
    "sistemapenale": _build_sistemapenale,
    "questionegiustizia": _build_questionegiustizia,
    "archiviopenale": _build_archiviopenale,
    "personaemercato": _build_personaemercato,
}


async def _build(sid: str) -> None:
    ix = _indexes[sid]
    ix.pages_ok = ix.pages_ko = 0
    try:
        items = P.dedupe(await BUILDERS[sid](ix))
        if items or not ix.items:
            ix.items = items
        ix.built_at = time.monotonic()
    except Exception as e:  # noqa: BLE001 - l'indice non deve mai bloccare il server
        ix.error = _err(e)
        ix.built_at = ix.built_at or time.monotonic()


def _ensure_index(sid: str) -> Index:
    ix = _indexes[sid]
    if (not ix.ready or ix.stale) and (ix.task is None or ix.task.done()):
        ix.task = asyncio.create_task(_build(sid))
    return ix


async def _wait_indexes(sids: list[str], wait: float) -> None:
    tasks = [_ensure_index(s).task for s in sids if s in _indexes]
    tasks = [t for t in tasks if t is not None and not t.done()]
    if tasks:
        await asyncio.wait(tasks, timeout=wait)


def _coverage(sid: str) -> str:
    ix = _indexes.get(sid)
    if ix is None:
        return "ricerca in tempo reale sul sito"
    if not ix.ready:
        return "indice in costruzione: riprova tra un minuto per risultati completi"
    dates = sorted(d for d in (it.get("data") for it in ix.items) if d)
    per = f", dal {dates[0]} al {dates[-1]}" if dates else ""
    extra = f"; {ix.pages_ko} pagine non lette ({ix.error})" if ix.pages_ko else ""
    return f"indice di {len(ix.items)} documenti{per}{extra}"


# ---------------------------------------------------------------- ricerche in tempo reale
async def _judicium(query: str | None, n: int = 20) -> list[dict]:
    base = config.SOURCES["judicium"]["base"]
    params = {"categories": config.JUDICIUM_FREE_CATEGORY, "per_page": min(n, 50),
              "_fields": "id,date,link,title,categories"}
    if query:
        params["search"] = query
    data, _ = await fetch_json(f"{base}/wp-json/wp/v2/posts", params)
    return [{**it, "_live": bool(query)} for it in P.jud_items(data) if it["accesso_libero"]]


async def _aic(query: str | None) -> list[dict]:
    base = config.SOURCES["rivistaaic"]["base"]
    if query:
        html = await fetch_text(f"{base}/it/component/search/",
                                {"searchword": query, "searchphrase": "all", "limit": 50})
    else:
        html = await fetch_text(f"{base}/it/rivista/ultimi-contributi-pubblicati")
    return [{**it, "_live": bool(query)} for it in P.aic_parse_list(html)]


def _resolve_fonti(fonti: list[str] | str | None) -> tuple[list[str], list[str]]:
    if not fonti:
        return list(config.SOURCES), []
    if isinstance(fonti, str):
        fonti = [f for f in re.split(r"[,;]", fonti) if f.strip()]
    ok, bad = [], []
    for f in fonti:
        key = P.norm(f)
        sid = (config.SOURCE_ALIAS.get(key) or config.SOURCE_ALIAS.get(key.replace(" ", ""))
               or (key.replace(" ", "") if key.replace(" ", "") in config.SOURCES else None))
        (ok if sid else bad).append(sid or f)
    return list(dict.fromkeys(ok)), bad


def _public(it: dict) -> dict:
    out = {
        "rivista": config.SOURCES[it["fonte"]]["nome"],
        "tipo": it.get("tipo"),
        "titolo": it.get("titolo"),
        "autori": it.get("autori") or None,
        "data": it.get("data"),
        "url": it.get("url"),
    }
    for k in ("fascicolo", "sezione", "data_decisione"):
        if it.get(k):
            out[k] = it[k]
    if it.get("dal_sitemap"):
        out["nota"] = "titolo ricavato dall'indirizzo: leggere il contributo per gli estremi esatti"
    if "_score" in it:
        out["pertinenza"] = it["_score"]
    if "corrispondenza" in it:
        out["corrispondenza"] = it["corrispondenza"]
    return out


async def _live(sid: str, query: str | None) -> tuple[list[dict], str | None]:
    try:
        if sid == "judicium":
            return await _judicium(query), None
        return await _aic(query), None
    except (httpx.HTTPError, PermissionError, ValueError) as e:
        return [], _err(e)


# ---------------------------------------------------------------- strumenti MCP
@mcp.tool()
async def elenca_fonti() -> dict:
    """Elenca le riviste coperte (livello A, con copertura attuale e limiti) e quelle
    soltanto segnalate (livelli B e C, che il connettore non legge)."""
    a = []
    for sid, s in config.SOURCES.items():
        a.append({"id": sid, "rivista": s["nome"], "sito": s["base"], "materie": s["materie"],
                  "licenza": s["licenza"], "note": s["note"], "copertura": _coverage(sid)})
    return {"livello_A_lettura_consentita": a,
            "livelli_B_C_solo_segnalazione": config.OTHER_SOURCES,
            "versione": config.VERSION}


@mcp.tool()
async def cerca_dottrina(
    query: str = "",
    fonti: list[str] | None = None,
    autore: str | None = None,
    anno: int | None = None,
    max_risultati: int = 15,
) -> dict:
    """Cerca saggi, note a sentenza e commenti nelle riviste ad accesso libero.

    query: parole chiave (istituto, norma, tema), es. "interrogatorio preventivo"
        o "fideiussioni omnibus". Il confronto avviene su titolo, autori e indirizzo.
    fonti: elenco facoltativo tra sistemapenale, questionegiustizia, archiviopenale,
        judicium, personaemercato, rivistaaic (accetta anche "SP", "QG", "AIC"...).
    autore: cognome dell'autore. anno: anno di pubblicazione.
    Alla prima ricerca gli indici vengono costruiti in background (circa un minuto):
    la risposta indica la copertura di ogni rivista.
    """
    if not (query or autore):
        return {"errore": "indica almeno `query` o `autore`"}
    sids, bad = _resolve_fonti(fonti)
    if not sids:
        return {"errore": f"fonti non riconosciute: {bad}", "fonti_valide": list(config.SOURCES)}
    idx = [s for s in sids if s in _indexes]
    live = [s for s in sids if s in LIVE]
    for s in idx:
        _ensure_index(s)
    live_q = query or autore
    live_res = await asyncio.gather(*[_live(s, live_q) for s in live])
    await _wait_indexes(idx, wait=25)
    pool: list[dict] = []
    for s in idx:
        pool += _indexes[s].items
    errori = {}
    for s, (items, err) in zip(live, live_res):
        pool += items
        if err:
            errori[config.SOURCES[s]["nome"]] = err
    ranked = P.rank(P.dedupe(pool), query, autore=autore, anno=anno)
    n = max(1, min(int(max_risultati or 15), 50))
    res = {
        "query": query, "autore": autore, "anno": anno,
        "totale_trovati": len(ranked),
        "risultati": [_public(it) for it in ranked[:n]],
        "copertura": {config.SOURCES[s]["nome"]: _coverage(s) for s in sids},
        "avvertenza": ("Solo fonti ad accesso libero. Verifica estremi e contenuto con "
                       "`leggi_contributo`; cita autore, titolo, rivista, data e URL."),
    }
    if bad:
        res["fonti_non_riconosciute"] = bad
    if errori:
        res["errori"] = errori
    if not ranked:
        res["suggerimento"] = ("Nessun risultato: prova parole diverse o meno parole, togli "
                               "`anno`, oppure consulta a mano le fonti di livello B/C "
                               "(vedi `elenca_fonti`), in particolare DoGi per la bibliografia.")
    return res


@mcp.tool()
async def ultime_pubblicazioni(fonti: list[str] | None = None, n: int = 10) -> dict:
    """Ultimi contributi pubblicati, per rivista (data più recente prima)."""
    sids, bad = _resolve_fonti(fonti)
    n = max(1, min(int(n or 10), 30))
    idx = [s for s in sids if s in _indexes]
    for s in idx:
        _ensure_index(s)
    live = [s for s in sids if s in LIVE]
    live_res = await asyncio.gather(*[_live(s, None) for s in live])
    await _wait_indexes(idx, wait=25)
    out = {}
    for s in idx:
        items = sorted((it for it in _indexes[s].items if it.get("data")),
                       key=lambda x: x["data"], reverse=True)
        out[config.SOURCES[s]["nome"]] = [_public(it) for it in items[:n]] or _coverage(s)
    for s, (items, err) in zip(live, live_res):
        items = sorted(items, key=lambda x: x.get("data") or "", reverse=True)
        out[config.SOURCES[s]["nome"]] = [_public(it) for it in items[:n]] or (err or "nessun dato")
    res = {"ultime": out}
    if bad:
        res["fonti_non_riconosciute"] = bad
    return res


async def _leggi(url: str) -> dict:
    host = _host(url)
    sid = SOURCE_HOSTS.get(host)
    if sid is None:
        other = OTHER_HOSTS.get(host)
        if other:
            return {"non_letto": True, "rivista": other["nome"], "livello": other["livello"],
                    "motivo": other["motivo"],
                    "indicazione": "Fonte non leggibile dal connettore: segnala il link all'utente."}
        return {"errore": f"{host} non è una fonte di questo connettore. Usa `elenca_fonti`."}

    s = config.SOURCES[sid]
    base = {"rivista": s["nome"], "url": url, "licenza": s["licenza"]}

    if sid == "judicium":
        slug = urlparse(url).path.strip("/").split("/")[-1]
        api = f"{s['base']}/wp-json/wp/v2/posts"
        data, _ = await fetch_json(api, {"slug": slug, "_fields": "id,date,link,title,categories"})
        if not data:
            return {**base, "errore": "contributo non trovato su Judicium"}
        post = data[0]
        titolo = P.clean(BeautifulSoup(post["title"]["rendered"], "html.parser").get_text(" "))
        if config.JUDICIUM_FREE_CATEGORY not in (post.get("categories") or []):
            return {**base, "titolo": titolo, "data": post.get("date", "")[:10], "non_letto": True,
                    "motivo": ("Contributo dei fascicoli di Judicium, riservato agli abbonati: il "
                               "connettore non ne legge il testo. Segnala il link all'utente.")}
        full, _ = await fetch_json(api, {"slug": slug, "_fields": "content"})
        html = full[0]["content"]["rendered"]
        text = BeautifulSoup(html, "html.parser").get_text("\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return {**base, "titolo": titolo, "data": post.get("date", "")[:10], "formato": "html",
                "_testo": text}

    if sid == "sistemapenale":
        page = url if "out=print" in url else url.split("#")[0] + ("&" if "?" in url else "?") + "out=print"
        m = html_main(await fetch_text(page), url)
        head = m["testo"][:200]
        return {**base, "titolo": P.clean_title(m["titolo"]), "autori": None,
                "data": P.parse_date(head), "formato": "html", "_testo": m["testo"]}

    if sid == "questionegiustizia":
        m = html_main(await fetch_text(url), url)
        autori = [P.clean_author(a) for a in m["autori"]] or None
        return {**base, "titolo": P.clean_title(m["titolo"]), "autori": autori, "data": m["data"],
                "formato": "html", "_testo": m["testo"]}

    if sid == "archiviopenale":
        html = await fetch_text(url)
        m = html_main(html, url)
        acc = P.ap_access(html)
        info = {**base, "titolo": P.clean_title(m["titolo"]), "autori": m["autori"] or None,
                "data": P.parse_labeled_date(m["testo"]) or m["data"]}
        is_article = "/articoli/" in url
        if is_article and not acc["open_access"]:
            return {**info, "non_letto": True, "abstract_o_pagina": m["testo"][:3000],
                    "motivo": "Contributo non marcato 'open access' (rivista a stampa in abbonamento)."}
        if acc["download"]:
            try:
                kind, body = await fetch_doc(acc["download"])
            except (httpx.HTTPError, PermissionError, ValueError) as e:
                kind, body = "errore", _err(e)
            if kind == "pdf" and body:
                return {**info, "formato": "pdf", "documento": acc["download"],
                        "pagina": m["testo"][:1500], "_testo": body}
            info["nota"] = ("Il testo integrale non è scaricabile senza accesso al sito: "
                            "restituisco la pagina (abstract o massima).")
        return {**info, "formato": "html", "_testo": m["testo"]}

    if sid == "rivistaaic":
        if url.lower().endswith(".pdf"):
            kind, body = await fetch_doc(url)
            return {**base, "formato": kind, "_testo": body}
        html = await fetch_text(url)
        m = html_main(html, url)
        # i meta autore/data delle pagine AIC sono del sito, non del contributo: autore dall'URL
        seg = urlparse(url).path.rstrip("/").split("/")
        autore = [P.clean(seg[-2].replace("-", " ")).title()] if len(seg) >= 2 else None
        info = {**base, "titolo": P.clean_title(m["titolo"]), "autori": autore, "data": None}
        pdf = P.aic_pdf_link(html)
        if pdf:
            kind, body = await fetch_doc(pdf)
            if kind == "pdf" and body:
                head = body[:1500]
                info["data"] = P.parse_labeled_date(head)
                fasc = P.parse_fascicolo(head)
                if fasc:
                    info["fascicolo"] = fasc
                return {**info, "formato": "pdf", "documento": pdf, "abstract": m["testo"][:2000],
                        "_testo": body}
        return {**info, "formato": "html", "_testo": m["testo"]}

    # personaemercato
    if url.lower().endswith(".pdf"):
        kind, body = await fetch_doc(url)
        meta = next((it for it in _indexes["personaemercato"].items if it["url"] == url), None)
        extra = {"titolo": meta["titolo"], "autori": meta["autori"], "fascicolo": meta.get("fascicolo")} if meta else {}
        return {**base, **extra, "formato": kind, "_testo": body}
    m = html_main(await fetch_text(url), url)
    return {**base, "titolo": m["titolo"], "data": m["data"], "formato": "html", "_testo": m["testo"]}


def _index_meta(url: str) -> dict | None:
    """Metadati dell'elemento con lo stesso URL negli indici (se presenti)."""
    def k(u: str) -> str:
        u = u.split("#")[0].replace("?out=print", "").replace("&out=print", "")
        return u.replace("http://", "https://").rstrip("/")
    target = k(url)
    for ix in _indexes.values():
        for it in ix.items:
            if k(it.get("url", "")) == target:
                return it
    return None


@mcp.tool()
async def leggi_contributo(url: str, da_carattere: int = 0,
                           max_caratteri: int = config.MAX_CARATTERI_DEFAULT) -> dict:
    """Legge un contributo di una rivista di livello A (pagina HTML o PDF), a blocchi.

    url: indirizzo restituito da `cerca_dottrina`, `ultime_pubblicazioni` o da una ricerca web.
    da_carattere / max_caratteri: per testi lunghi richiama con da_carattere =
    prossimo_da_carattere. I contributi riservati agli abbonati (fascicoli di Judicium,
    rivista a stampa di Archivio Penale) non vengono letti: ne restituisce solo gli estremi.
    Riassumi con parole tue; non riprodurre lunghi passi.
    """
    key = "leggi:" + url
    res = _cache_get(key)
    if res is None:
        try:
            res = await _leggi(url.strip())
        except PermissionError as e:
            return {"url": url, "non_letto": True, "motivo": str(e)}
        except (httpx.HTTPError, ValueError) as e:
            return {"url": url, "errore": _err(e)}
        meta = _index_meta(url)
        if meta and "errore" not in res:
            # gli elenchi della rivista danno titolo, autori e data più affidabili dei meta della pagina
            for k in ("titolo", "autori", "data", "fascicolo", "data_decisione"):
                if meta.get(k) and not (k == "titolo" and meta.get("dal_sitemap")):
                    res[k] = meta[k]
        if "_testo" in res:
            _cache_put(key, res)
    out = {k: v for k, v in res.items() if k != "_testo"}
    if "_testo" in res:
        out.update(_slice(res["_testo"], da_carattere, max_caratteri))
        if not res["_testo"].strip():
            out["nota"] = "Testo non estraibile (pagina dinamica o PDF scansionato): apri il link."
    return out


@mcp.tool()
async def commenti_a_sentenza(estremi: str, fonti: list[str] | None = None) -> dict:
    """Trova note e commenti che citano una decisione nel titolo o nell'indirizzo.

    estremi: es. "Cass. SS.UU. n. 24825/2026", "Corte cost. n. 108 del 2026",
        "Cass., Sez. III, 19 febbraio 2026". Servono almeno il numero o la data.
    Corrispondenza "forte" = numero e anno citati; "possibile" = solo numero (o organo+data).
    """
    est = P.parse_estremi(estremi)
    if not est["numero"] and not est["data"]:
        return {"errore": "indica almeno il numero della decisione o la data completa"}
    sids, bad = _resolve_fonti(fonti)
    idx = [s for s in sids if s in _indexes]
    live = [s for s in sids if s in LIVE]
    for s in idx:
        _ensure_index(s)
    q = est["numero"] or estremi
    live_res = await asyncio.gather(*[_live(s, q) for s in live])
    await _wait_indexes(idx, wait=25)
    pool: list[dict] = []
    for s in idx:
        pool += _indexes[s].items
    for items, _ in live_res:
        pool += items
    found = []
    for it in P.dedupe(pool):
        m = P.match_decisione(it, est)
        if m:
            found.append({**it, "corrispondenza": m})
    found.sort(key=lambda x: (x["corrispondenza"] == "forte", x.get("data") or ""), reverse=True)
    res = {
        "decisione": {k: est[k] for k in ("organo", "numero", "anno", "data")},
        "commenti": [_public(it) for it in found[:30]],
        "copertura": {config.SOURCES[s]["nome"]: _coverage(s) for s in sids},
        "nota": ("Il confronto avviene su titoli e indirizzi: una nota che non cita gli "
                 "estremi nel titolo non viene trovata. Verifica sempre con `leggi_contributo`."),
    }
    if not found:
        res["suggerimento"] = ("Nessun commento trovato: prova `cerca_dottrina` con l'istituto "
                               "trattato, oppure il connettore ilcaso.it (`commenti_a_sentenza`).")
    if bad:
        res["fonti_non_riconosciute"] = bad
    return res


# ---------------------------------------------------------------------- Main
async def _probe(query: str) -> dict:
    for s in _indexes:
        _ensure_index(s)
    await _wait_indexes(list(_indexes), wait=600)
    return await cerca_dottrina(query)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", help="esegue una ricerca di prova e stampa il JSON")
    ap.add_argument("--leggi", help="legge un contributo e stampa il JSON")
    args = ap.parse_args()
    if args.probe:
        print(json.dumps(asyncio.run(_probe(args.probe)), ensure_ascii=False, indent=2))
    elif args.leggi:
        print(json.dumps(asyncio.run(leggi_contributo(args.leggi)), ensure_ascii=False, indent=2))
    else:
        mcp.run(transport=os.getenv("MCP_TRANSPORT", "streamable-http"))
