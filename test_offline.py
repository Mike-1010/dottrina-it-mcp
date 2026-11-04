"""Collaudo offline di dottrina-it-mcp.

Le pagine di prova riproducono le strutture osservate sui siti il 04/11/2026 (forma degli
URL, elenchi, marcature 'open access', API REST di WordPress). Nessun accesso alla rete:
il client HTTP del server è sostituito da un trasporto simulato.

Esecuzione:  python tests/test_offline.py   (richiede reportlab solo per creare i PDF di prova)
"""
import asyncio
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx  # noqa: E402

import parsers as P  # noqa: E402
import server as S  # noqa: E402


def make_pdf(text: str) -> bytes:
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    y = 800
    for line in text.split("\n"):
        c.drawString(40, y, line)
        y -= 16
    c.save()
    return buf.getvalue()


# ------------------------------------------------------------------ pagine di prova
SP_ROBOTS = "User-agent: *\nDisallow: /tool/\nsitemap: https://www.sistemapenale.it/sitemap.xml\n"
SP_LIST = """<html><body><div class="lista">
<div class="item"><span class="tipo">Scheda</span><span class="data">04 Novembre 2026</span>
 <h3><a href="https://www.sistemapenale.it/it/scheda/zuffada-lart-4-bis-ord-penit-di-nuovo-al-vaglio-di-strasburgo">L'art. 4-bis ord. penit. di nuovo al vaglio di Strasburgo</a></h3>
 <a href="https://www.sistemapenale.it/it/autori-di-sp/zuffada-edoardo">Edoardo Zuffada</a></div>
<div class="item"><span class="tipo">Articolo</span><span class="data">27 Ottobre 2026</span>
 <h3><a href="/it/scheda/lazzarini-linterrogatorio-preventivo-nei-procedimenti-soggettivamente-cumulativi-e-il-regime-della-nullita-i-chiarimenti-delle-sezioni-unite">L'interrogatorio preventivo nei procedimenti soggettivamente cumulativi e il regime della nullità: i chiarimenti delle Sezioni Unite</a></h3>
 <a href="/it/autori-di-sp/lazzarini-francesco">Francesco Lazzarini</a></div>
<div class="item"><span class="tipo">Notizie</span><span class="data">15 Ottobre 2026</span>
 <h3><a href="/it/notizie/la-consulta-rimette-a-se-stessa-la-qlc-sulla-causa-di-non-punibilita-di-cui-allart-649-cp">Delitti contro il patrimonio: la Consulta si autorimette la q.l.c. sull'art. 649 c.p.</a></h3></div>
</div><a href="/it/contributi?page=2">NEXT</a></body></html>"""
SP_SITEMAP = """<?xml version="1.0" encoding="UTF-8"?><urlset>
<url><loc>https://www.sistemapenale.it/it</loc></url>
<url><loc>https://www.sistemapenale.it/it/articolo/mazzacuva-manes-corte-cost-32-del-2020-irretroattivita-esecuzione-penale</loc></url>
<url><loc>https://www.sistemapenale.it/it/articolo/vasta-le-su-sui-mezzi-impugnazione-misure-sicurezza-condanna-giudizio-abbreviato</loc></url>
<url><loc>https://www.sistemapenale.it/it/scheda/lazzarini-linterrogatorio-preventivo-nei-procedimenti-soggettivamente-cumulativi-e-il-regime-della-nullita-i-chiarimenti-delle-sezioni-unite</loc></url>
</urlset>"""
SP_ARTICLE = """<html><head><title>F. Lazzarini | L'interrogatorio preventivo | Sistema Penale | SP</title>
<meta name="author" content="Francesco Lazzarini"></head><body><header>menu</header>
<article><h1>L'interrogatorio preventivo nei procedimenti soggettivamente cumulativi</h1>
<p>1. Le Sezioni Unite hanno chiarito il regime della nullità derivante dall'omesso interrogatorio preventivo nei procedimenti con più indagati.</p>
<p>2. La soluzione adottata distingue la posizione del coindagato non interrogato da quella degli altri, limitando l'invalidità alla misura che lo riguarda.</p>
<p>3. Restano aperti i problemi di coordinamento con la disciplina delle misure cautelari reali.</p>
</article><footer>footer</footer></body></html>"""

QG_LIST = """<html><body>
<div class="art"><a href="/articolo/la-sentenza-n-157-della-corte-costituzionale-in-tema-di-trattamento-sanitario-obbligatorio">/articolo/la-sentenza-n-157-della-corte-costituzionale-in-tema-di-trattamento-sanitario-obbligatorio</a>
 <a href="/articolo/la-sentenza-n-157-della-corte-costituzionale-in-tema-di-trattamento-sanitario-obbligatorio">Leggi e istituzioni</a>
 <a href="/articolo/la-sentenza-n-157-della-corte-costituzionale-in-tema-di-trattamento-sanitario-obbligatorio">La sentenza n. 157 della Corte Costituzionale in tema di Trattamento Sanitario Obbligatorio</a>
 di <a href="/autore/pietro-pellegrini">Pietro Pellegrini</a> <span>03/11/2026</span></div>
<div class="art"><a href="/articolo/i-nodi-irrisolti-dei-magistrati-onorari-stabilizzati">I nodi irrisolti dei magistrati onorari stabilizzati, tra Unione europea, diritto nazionale e normativa secondaria</a>
 di <a href="/autore/bruno-giangiacomo">Bruno Giangiacomo</a> , <a href="/autore/daniela-cavallini">Daniela Cavallini</a> <span>02/11/2026</span></div>
</body></html>"""

AP_FASC_LIST = """<html><body><ul>
<li><a href="https://archiviopenale.it/fascicolo-n-3-%E2%80%93-settembre-dicembre-2026-%28web%29/fascicoli/51065">Fascicolo n. 3 – Settembre-Dicembre 2026 (Web)</a></li>
<li><a href="https://archiviopenale.it/fascicolo-n-2-%E2%80%93-maggio-agosto-2023/fascicoli/2462">Fascicolo n. 2 – Maggio-Agosto 2023</a></li>
</ul></body></html>"""
AP_FASC = """<html><body>
<div class="art"><span>articolo pubblicato | open access</span><p>Samuel Bolis</p>
 <h4><a href="/red-flags-segnalazioni-antiriciclaggio-in-mala-fede-vuoti-sanzionatori-e-tutela-del-soggetto-segnalato/articoli/51078">Red Flags. Segnalazioni antiriciclaggio in mala fede, vuoti sanzionatori e tutela del soggetto segnalato</a></h4>
 <p>Pubblicato il 30 October 2026</p></div>
<div class="art"><span>articolo pubblicato | open access</span><p>Pier Paolo Paulesu</p>
 <h4><a href="/la-riapertura-delle-indagini-e-il-rischio-del-doppio-errore-investigativo/articoli/51072">La riapertura delle indagini e il rischio del doppio errore investigativo</a></h4>
 <p>Pubblicato il 9 ottobre 2026</p></div>
</body></html>"""
AP_SECTION = """<html><body>
<div><h4><a href="/interrogatorio-preventivo--cass-sez-iii-19-febbraio-2026/contenuti/31874">Interrogatorio preventivo - Cass., Sez. III, 19 febbraio 2026</a></h4></div>
<div><h4><a href="/ordine-europeo-indagine--cass-sez-vi-22-luglio-2026/contenuti/31873">Ordine Europeo Indagine - Cass., Sez. VI, 22 luglio 2026, Sky ECC</a></h4></div>
</body></html>"""
AP_OPEN = """<html><head><title>Red Flags</title></head><body><article>
<h1>Red Flags. Segnalazioni antiriciclaggio in mala fede</h1><p>Samuel Bolis</p>
<p>articolo pubblicato | open access</p><p>Abstract: il contributo esamina le segnalazioni di operazioni sospette presentate in mala fede e i vuoti sanzionatori.</p>
<a href="/File/DownloadArticolo?codice=b8b47915&amp;idarticolo=51078">Visualizza</a>
<a href="/Account/Login">Accedi</a></article></body></html>"""
AP_PAID = """<html><head><title>Saggio a stampa</title></head><body><article>
<h1>Saggio della rivista a stampa</h1><p>Abstract breve del saggio a stampa.</p>
<a href="/file/downloadarticolopagamento?codice=x&amp;idarticolo=999">Acquista</a></article></body></html>"""

AIC_ROBOTS = "User-agent: AhrefsBot\nDisallow: /\n\nUser-agent: *\nDisallow: /administrator/\nCrawl-delay: 10\n"
AIC_SEARCH = """<html><body><dl class="search-results">
<dt><a href="/it/rivista/ultimi-contributi-pubblicati/daniele-trabucco/autonomia-differenziata-alcuni-problemi-costituzionali">Autonomia differenziata: alcuni problemi costituzionali</a></dt>
<dd>Pubblicato: 18 marzo 2026</dd>
<dt><a href="/it/rivista/ultimi-contributi-pubblicati/daniela-mone/autonomia-differenziata-come-mezzo-di-unita-statale">Autonomia differenziata come mezzo di unità statale</a></dt>
<dd>Pubblicato: 19 marzo 2019</dd></dl></body></html>"""
AIC_ARTICLE = """<html><head><title>Autonomia differenziata</title></head><body><article>
<h1>Autonomia differenziata: alcuni problemi costituzionali</h1>
<p>Abstract: il saggio esamina la natura dell'intesa e la legge n. 86 del 2024.</p>
<a href="/images/rivista/pdf/1_2026_9_Trabucco.pdf">Visualizza</a></article></body></html>"""

JUD_SEARCH = [
    {"id": 45494, "date": "2026-09-21T02:24:53",
     "link": "https://www.judicium.it/fideiussioni-omnibus-note-a-caldo-sulla-sentenza-delle-ss-uu-n-24825-2026/",
     "title": {"rendered": "Fideiussioni omnibus: note &#8220;a caldo&#8221; sulla sentenza delle SS.UU. n. 24825/2026"},
     "categories": [60, 27]},
]
JUD_FREE_META = [{"id": 45494, "date": "2026-09-21T02:24:53", "link": JUD_SEARCH[0]["link"],
                  "title": JUD_SEARCH[0]["title"], "categories": [60, 27]}]
JUD_FREE_CONTENT = [{"content": {"rendered": "<p>1. Le Sezioni Unite hanno precisato l&#8217;ambito della nullità.</p><p>2. Conclusioni.</p>"}}]
JUD_PAID_META = [{"id": 1, "date": "2026-08-04T14:22:17",
                  "link": "https://www.judicium.it/sulla-calcolabilita-degli-esiti-dei-procedimenti-civili/",
                  "title": {"rendered": "Sulla calcolabilità degli esiti dei procedimenti civili"},
                  "categories": [7]}]

PEM_POSTS = [{"date": "2026-08-09T09:47:37", "link": "https://www.personaemercato.it/persona-e-mercato-numero-22026/",
              "title": {"rendered": "Persona e Mercato, numero 2/2026"},
              "content": {"rendered": (
                  "<p>Scarica il <a href='https://www.personaemercato.it/wp-content/uploads/2026/08/PeM-2-2026.pdf'>numero completo</a></p>"
                  "<p><strong>Saggi</strong></p><ul>"
                  "<li><a href='https://www.personaemercato.it/wp-content/uploads/2026/08/Vettori.pdf'>G. VETTORI, Giustizia contrattuale. Le diverse visioni</a></li>"
                  "<li><a href='https://www.personaemercato.it/wp-content/uploads/2026/08/Iamiceli.pdf'>P. IAMICELI, Mercati digitali, intelligenza artificiale e tutele contrattuali del consumatore</a></li></ul>"
                  "<p><strong>Commenti</strong></p><ul>"
                  "<li><a href='http://www.personaemercato.it/wp-content/uploads/2026/08/Gasparinetti.pdf'>F. GASPARINETTI, Autonomous vehicles and the duty of damage compensation</a></li></ul>")}}]

PDF_AIC = make_pdf("Rivista AIC 1/2026\nAutonomia differenziata: alcuni problemi costituzionali\nTesto del saggio sull'intesa.")
PDF_AP = make_pdf("Archivio Penale 2026\nRed Flags\nTesto integrale open access del contributo.")
PDF_PEM = make_pdf("Persona e Mercato 2/2026\nGiustizia contrattuale\nTesto del saggio di Vettori.")

CALLS: list[str] = []


def handler(request: httpx.Request) -> httpx.Response:
    u = str(request.url)
    CALLS.append(u)
    host = request.url.host
    path = request.url.path
    q = dict(request.url.params)
    html = lambda s: httpx.Response(200, text=s, headers={"content-type": "text/html; charset=utf-8"})  # noqa: E731
    js = lambda d, extra=None: httpx.Response(200, json=d, headers={"x-wp-totalpages": "1", **(extra or {})})  # noqa: E731
    pdf = lambda b: httpx.Response(200, content=b, headers={"content-type": "application/pdf"})  # noqa: E731

    if path == "/robots.txt":
        if "sistemapenale" in host:
            return httpx.Response(200, text=SP_ROBOTS, headers={"content-type": "text/plain"})
        if "rivistaaic" in host:
            return httpx.Response(200, text=AIC_ROBOTS, headers={"content-type": "text/plain"})
        if "personaemercato" in host:
            return httpx.Response(200, text="User-agent: *\nDisallow: /wp-admin/\n",
                                  headers={"content-type": "text/plain"})
        return httpx.Response(404, text="not found")
    if "sistemapenale" in host:
        if path == "/sitemap.xml":
            return httpx.Response(200, text=SP_SITEMAP, headers={"content-type": "application/xml"})
        if path == "/it/contributi":
            return html(SP_LIST if "page" not in q else "<html><body></body></html>")
        if path.startswith("/it/scheda/lazzarini"):
            assert q.get("out") == "print", "Sistema Penale va letto in versione stampabile"
            return html(SP_ARTICLE)
    if "questionegiustizia" in host and path.startswith("/cat/"):
        return html(QG_LIST if path == "/cat/leggieistituzioni" and "page" not in q else "<html></html>")
    if "archiviopenale" in host:
        if path == "/rivista-web/rivista/3":
            return html(AP_FASC_LIST)
        if path.endswith("/fascicoli/51065"):
            return html(AP_FASC)
        if "/sezioni/15" in path and "p" not in q:
            return html(AP_SECTION)
        if "/sezioni/" in path:
            return html("<html></html>")
        if path.endswith("/articoli/51078"):
            return html(AP_OPEN)
        if path.endswith("/articoli/999"):
            return html(AP_PAID)
        if path.lower() == "/file/downloadarticolo":
            return pdf(PDF_AP)
    if "judicium" in host and path == "/wp-json/wp/v2/posts":
        if "search" in q:
            assert q.get("categories") == "60", "Judicium: la ricerca deve limitarsi alla categoria 60"
            return js(JUD_SEARCH)
        if q.get("slug", "").startswith("fideiussioni"):
            if "content" in q.get("_fields", ""):
                return js(JUD_FREE_CONTENT)
            return js(JUD_FREE_META)
        if q.get("slug", "").startswith("sulla-calcolabilita"):
            assert "content" not in q.get("_fields", ""), "mai chiedere il testo di un saggio riservato"
            return js(JUD_PAID_META)
        return js(JUD_SEARCH)
    if "personaemercato" in host:
        if path == "/wp-json/wp/v2/posts":
            return js(PEM_POSTS)
        if path.endswith("Vettori.pdf"):
            return pdf(PDF_PEM)
    if "rivistaaic" in host:
        if path == "/it/component/search/":
            return html(AIC_SEARCH)
        if path.endswith("autonomia-differenziata-alcuni-problemi-costituzionali"):
            return html(AIC_ARTICLE)
        if path.endswith(".pdf"):
            return pdf(PDF_AIC)
        if path == "/it/rivista/ultimi-contributi-pubblicati":
            return html(AIC_SEARCH)
    return httpx.Response(404, text="non previsto: " + u)


SLEEPS: list[float] = []


async def fake_sleep(s):
    SLEEPS.append(s)


# ------------------------------------------------------------------ test dei parser
def test_parsers():
    sp = P.sp_parse_list(SP_LIST)
    assert len(sp) == 3, sp
    z = [i for i in sp if "zuffada" in i["url"]][0]
    assert z["tipo"] == "scheda" and z["data"] == "2026-11-04" and z["autori"] == ["Edoardo Zuffada"], z
    assert [i for i in sp if "consulta" in i["url"]][0]["tipo"] == "notizia"

    sm = P.sp_items_from_sitemap(SP_SITEMAP)
    assert len(sm) == 3 and all(i["dal_sitemap"] for i in sm)

    qg = P.qg_parse_list(QG_LIST)
    assert len(qg) == 2, qg
    t = [i for i in qg if "157" in i["url"]][0]
    assert t["titolo"].startswith("La sentenza n. 157"), t
    assert t["autori"] == ["Pietro Pellegrini"] and t["data"] == "2026-11-03", t
    n = [i for i in qg if "nodi" in i["url"]][0]
    assert n["autori"] == ["Bruno Giangiacomo", "Daniela Cavallini"], n

    fasc = P.ap_parse_fascicoli(AP_FASC_LIST)
    assert len(fasc) == 1 and fasc[0]["url"].endswith("/51065"), fasc  # solo i fascicoli web
    arts = P.ap_parse_articles(AP_FASC, fascicolo="3/2026")
    assert len(arts) == 2
    rf = [a for a in arts if "51078" in a["url"]][0]
    assert rf["data"] == "2026-10-30" and rf["autori"] == ["Samuel Bolis"], rf
    cont = P.ap_parse_contenuti(AP_SECTION)
    assert cont[0]["data_decisione"] == "2026-02-19" and cont[0]["data"] is None, cont

    # date nei titoli (decisioni, leggi, eventi) non vanno scambiate per date di pubblicazione
    moro = ('<dl><dt><a href="/it/rivista/ultimi-contributi-pubblicati/daniele-piccione/discorso-moro">'
            'Il discorso di Aldo Moro del 28 febbraio 1978</a></dt><dd>Estratto: legge 24 giugno 2024</dd></dl>')
    assert P.aic_parse_list(moro)[0]["data"] is None
    qg_old = ('<div><a href="/articolo/x">Commento alla legge 25 ottobre 1980</a> di '
              '<a href="/autore/y">Di Mario Rossi</a> <span>02/11/2026</span></div>')
    q = P.qg_parse_list(qg_old)[0]
    assert q["data"] == "2026-11-02" and q["autori"] == ["Mario Rossi"], q
    assert P.clean_title("F. Lazzarini | Titolo | Sistema Penale | SP") == "Titolo"

    assert P.ap_access(AP_OPEN)["open_access"] and "DownloadArticolo" in P.ap_access(AP_OPEN)["download"]
    paid = P.ap_access(AP_PAID)
    assert not paid["open_access"] and paid["download"] is None and paid["a_pagamento"]

    aic = P.aic_parse_list(AIC_SEARCH)
    assert len(aic) == 2 and aic[0]["data"] == "2026-03-18" and aic[0]["autori"] == ["Daniele Trabucco"], aic
    assert P.aic_pdf_link(AIC_ARTICLE).endswith("1_2026_9_Trabucco.pdf")

    pem = P.pem_items_from_issue(PEM_POSTS[0])
    assert len(pem) == 3, pem  # il PDF del numero completo non è un contributo
    v = pem[0]
    assert v["autori"] == ["G. Vettori"] and v["titolo"].startswith("Giustizia contrattuale"), v
    assert v["tipo"] == "saggi" and pem[2]["url"].startswith("https://"), pem

    est = P.parse_estremi("Cass. SS.UU. n. 24825/2026")
    assert est == {**est, "numero": "24825", "anno": "2026", "organo": "Sezioni Unite"}, est
    est2 = P.parse_estremi("Corte cost. n. 32 del 2020")
    assert est2["numero"] == "32" and est2["anno"] == "2020" and est2["organo"] == "Corte costituzionale"
    item = {"titolo": "", "url": "https://www.sistemapenale.it/it/articolo/mazzacuva-manes-corte-cost-32-del-2020-irretroattivita"}
    assert P.match_decisione(item, est2) == "forte"
    assert P.match_decisione({"titolo": "Altro tema 2020", "url": "x"}, est2) is None

    r = P.rank(sp + qg, "interrogatorio preventivo")
    assert r and "interrogatorio" in r[0]["url"], r
    assert P.rank(qg, "magistrati onorari")[0]["url"].endswith("stabilizzati")
    assert P.rank(qg, "", autore="Cavallini")[0]["url"].endswith("stabilizzati")
    print("parser: OK")


# ------------------------------------------------------------------ test end-to-end degli strumenti
async def test_tools():
    S._client = httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True,
                                  headers={"User-Agent": "test"})
    S.asyncio.sleep = fake_sleep  # niente attese reali; le attese richieste vengono registrate

    fonti = await S.elenca_fonti()
    assert len(fonti["livello_A_lettura_consentita"]) == 6 and len(fonti["livelli_B_C_solo_segnalazione"]) >= 8

    res = await S.cerca_dottrina("interrogatorio preventivo")
    urls = [r["url"] for r in res["risultati"]]
    assert any("lazzarini" in u for u in urls), res
    laz = [r for r in res["risultati"] if "lazzarini" in r["url"]][0]
    assert "nota" not in laz and laz["data"] == "2026-10-27", laz  # elenco preferito al sitemap
    assert all("costruzione" not in v for v in res["copertura"].values()), res["copertura"]
    print("cerca_dottrina:", json.dumps(res["risultati"][:2], ensure_ascii=False)[:300])

    res = await S.cerca_dottrina("autonomia differenziata", fonti=["AIC"])
    assert res["risultati"][0]["rivista"] == "Rivista AIC", res
    assert 10.0 in [round(x) for x in SLEEPS] or any(x >= 9 for x in SLEEPS), SLEEPS  # Crawl-delay 10 rispettato

    res = await S.cerca_dottrina("giustizia contrattuale", fonti="personaemercato")
    assert res["risultati"][0]["autori"] == ["G. Vettori"], res

    res = await S.commenti_a_sentenza("Cass. SS.UU. n. 24825/2026")
    assert res["commenti"] and res["commenti"][0]["rivista"] == "Judicium", res
    assert res["commenti"][0]["corrispondenza"] == "forte"
    res = await S.commenti_a_sentenza("Corte cost. n. 32 del 2020", fonti=["SP"])
    assert res["commenti"][0]["corrispondenza"] == "forte" and "nota" in res["commenti"][0], res

    ult = await S.ultime_pubblicazioni(n=3)
    assert ult["ultime"]["Sistema Penale"][0]["data"] == "2026-11-04", ult

    # lettura: Sistema Penale (versione stampabile)
    r = await S.leggi_contributo(laz["url"], max_caratteri=500)
    assert "Sezioni Unite" in r["testo"] and r["formato"] == "html", r

    # lettura: Judicium libero vs riservato
    r = await S.leggi_contributo(JUD_SEARCH[0]["link"])
    assert "nullità" in r["testo"], r
    r = await S.leggi_contributo(JUD_PAID_META[0]["link"])
    assert r.get("non_letto") and "testo" not in r, r

    # lettura: Archivio Penale open access (PDF) vs a pagamento
    r = await S.leggi_contributo("https://archiviopenale.it/red-flags-segnalazioni-antiriciclaggio-in-mala-fede-vuoti-sanzionatori-e-tutela-del-soggetto-segnalato/articoli/51078")
    assert r["formato"] == "pdf" and "open access" in r["testo"], r
    r = await S.leggi_contributo("https://archiviopenale.it/saggio/articoli/999")
    assert r.get("non_letto") and "testo" not in r, r
    assert not any("pagamento" in c.lower() for c in CALLS), "mai scaricare file a pagamento"

    # lettura: Rivista AIC (PDF) e Persona e Mercato (PDF)
    r = await S.leggi_contributo("https://www.rivistaaic.it/it/rivista/ultimi-contributi-pubblicati/daniele-trabucco/autonomia-differenziata-alcuni-problemi-costituzionali")
    assert r["formato"] == "pdf" and "intesa" in r["testo"], r
    r = await S.leggi_contributo("https://www.personaemercato.it/wp-content/uploads/2026/08/Vettori.pdf")
    assert r["formato"] == "pdf" and r["autori"] == ["G. Vettori"], r

    # fonti di livello B/C e domini estranei: mai lette
    n_calls = len(CALLS)
    r = await S.leggi_contributo("https://www.juscivile.it/qualcosa")
    assert r["non_letto"] and r["livello"] == "C", r
    r = await S.leggi_contributo("https://federalismi.it/nv14/articolo-documento.cfm?Artid=1")
    assert r["non_letto"] and r["livello"] == "B", r
    r = await S.leggi_contributo("https://example.com/x")
    assert "errore" in r, r
    assert len(CALLS) == n_calls, "nessuna richiesta verso fonti B/C o domini estranei"

    # blocchi successivi
    r1 = await S.leggi_contributo(laz["url"], max_caratteri=500)
    if r1["prossimo_da_carattere"]:
        r2 = await S.leggi_contributo(laz["url"], da_carattere=r1["prossimo_da_carattere"])
        assert r2["da_carattere"] == r1["prossimo_da_carattere"]
    print("strumenti: OK")


if __name__ == "__main__":
    test_parsers()
    asyncio.run(test_tools())
    print("TUTTI I TEST SUPERATI")
