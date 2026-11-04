"""Configurazione del connettore dottrina-it-mcp. Modifica qui, non in server.py.

Ogni informazione sui siti riporta la data e il metodo con cui è stata verificata.
Verifiche del 04/11/2026, svolte leggendo robots.txt, pagine ed elenchi pubblici.
"""
import os

VERSION = "0.1.4"

# Identificati in modo onesto. Per aggiungere un contatto imposta DOTTRINA_UA su Render
# (es. "dottrina-it-mcp/0.1 (uso professionale; contatto: indirizzo@studio.it)").
USER_AGENT = os.getenv("DOTTRINA_UA", f"dottrina-it-mcp/{VERSION} (uso professionale personale)")

MIN_INTERVAL = float(os.getenv("DOTTRINA_MIN_INTERVAL", "1.5"))  # secondi tra richieste allo stesso sito
CACHE_TTL = 900          # secondi di cache delle pagine
CACHE_MAX = 300          # voci massime in cache (RAM limitata su Render free)
INDEX_TTL = 6 * 3600     # dopo 6 ore gli indici vengono aggiornati
TIMEOUT = 25
PDF_MAX_BYTES = 15 * 1024 * 1024
PDF_MAX_PAGES = 250
MAX_CARATTERI_DEFAULT = 8000

# Quanto scorrere gli elenchi per costruire gli indici (alla prima ricerca, in background).
SP_LIST_PAGES = int(os.getenv("SP_LIST_PAGES", "15"))       # 10 contributi per pagina
QG_PAGES = int(os.getenv("QG_PAGES", "3"))                  # 28 articoli per pagina, per categoria
AP_FASCICOLI = int(os.getenv("AP_FASCICOLI", "12"))         # fascicoli web più recenti
AP_SECTION_PAGES = int(os.getenv("AP_SECTION_PAGES", "2"))

# ---------------------------------------------------------------- Fonti di livello A
# Livello A = lettura del testo integrale su richiesta consentita (una pagina alla volta).
SOURCES = {
    "sistemapenale": {
        "nome": "Sistema Penale",
        "base": "https://www.sistemapenale.it",
        "materie": ["penale", "processo penale", "esecuzione penale", "europeo"],
        "licenza": "CC BY-NC-ND 4.0",
        # 04/11/2026: robots.txt vieta solo /tool/; sitemap.xml completa (circa 1,6 MB);
        # elenco /it/contributi?page=N (10 per pagina, con tipo, data, autori);
        # la pagina /it/cerca restituisce un errore PHP (ricerca del sito non utilizzabile);
        # versione stampabile: URL + "?out=print".
        "note": "Indice da sitemap + ultimi contributi; ricerca interna del sito non funzionante.",
    },
    "questionegiustizia": {
        "nome": "Questione Giustizia",
        "base": "https://www.questionegiustizia.it",
        "materie": ["ordinamento giudiziario", "riforme", "lavoro", "famiglia", "immigrazione",
                    "costituzionale", "penale", "civile"],
        "licenza": "© Questione Giustizia (nessuna licenza aperta dichiarata)",
        # 04/11/2026: robots.txt senza restrizioni; sitemap.xml non disponibile;
        # elenchi /cat/<categoria>?page=N (28 articoli per pagina, con data gg/mm/aaaa e autori).
        "note": "Indice dalle ultime pagine di ogni categoria.",
    },
    "archiviopenale": {
        "nome": "Archivio Penale",
        "base": "https://archiviopenale.it",
        "materie": ["penale", "processo penale", "europeo"],
        "licenza": "© degli autori; contributi web marcati 'open access'",
        # 04/11/2026: robots.txt non presente; sitemap ferma al 2017;
        # elenco completo dei fascicoli web in /rivista-web/rivista/3;
        # articolo: /<slug>/articoli/<id>, testo da File/DownloadArticolo se 'open access';
        # la rivista a stampa è in abbonamento (link 'downloadarticolopagamento'): mai letta.
        "note": "Solo contributi della rivista web marcati 'open access'.",
    },
    "judicium": {
        "nome": "Judicium",
        "base": "https://www.judicium.it",
        "materie": ["processo civile", "esecuzione", "arbitrato", "famiglia", "crisi d'impresa"],
        "licenza": "© Pacini Giuridica",
        # 04/11/2026: WordPress; API REST pubblica; categoria 'Aggiornamenti' = id 60
        # (ad accesso libero). I saggi dei fascicoli sono in abbonamento: mai letti.
        "note": "Solo la categoria 'Aggiornamenti' (id 60), ad accesso libero.",
    },
    "personaemercato": {
        "nome": "Persona e Mercato",
        "base": "https://www.personaemercato.it",
        "materie": ["civile", "contratti", "persona", "mercato digitale", "consumatori"],
        "licenza": "Riproduzione consentita con indicazione della fonte",
        # 04/11/2026: WordPress; robots.txt chiude solo /wp-admin/; ogni numero è un post
        # (categoria 12) con l'elenco dei PDF dei contributi ("AUTORE, Titolo").
        "note": "Indice dai post dei numeri; testi in PDF.",
    },
    "rivistaaic": {
        "nome": "Rivista AIC",
        "base": "https://www.rivistaaic.it",
        "materie": ["costituzionale", "pubblico", "europeo"],
        "licenza": "Nessuna licenza dichiarata nelle pagine",
        # 04/11/2026: Joomla; robots.txt con Crawl-delay: 10; ricerca
        # /it/component/search/?searchword=...&searchphrase=all; testi in PDF
        # (/images/rivista/pdf/...).
        "note": "Ricerca del sito; il robots.txt chiede 10 secondi tra le richieste.",
    },
}

JUDICIUM_FREE_CATEGORY = 60

QG_CATEGORIES = [
    "leggieistituzioni", "magistraturaesocieta", "osservatoriointernazionale", "strumenti",
    "giurisprudenzaedocumenti", "dirittisenzaconfini", "spilli",
]

# Sezioni di Archivio Penale con note e decisioni (contenuti): id sezione.
AP_SECTIONS = {
    "giurisprudenza-di-legittimita": 15,
    "giurisprudenza-europea": 400,
    "giurisprudenza-costituzionale": 390,
    "giurisprudenza-di-merito": 405,
}

PEM_ISSUE_CATEGORY = 12

# Nomi colloquiali -> id fonte
SOURCE_ALIAS = {
    "sp": "sistemapenale", "sistema penale": "sistemapenale", "sistemapenale": "sistemapenale",
    "qg": "questionegiustizia", "questione giustizia": "questionegiustizia",
    "questionegiustizia": "questionegiustizia",
    "ap": "archiviopenale", "archivio penale": "archiviopenale", "archiviopenale": "archiviopenale",
    "judicium": "judicium",
    "pem": "personaemercato", "persona e mercato": "personaemercato",
    "personaemercato": "personaemercato",
    "aic": "rivistaaic", "rivista aic": "rivistaaic", "rivistaaic": "rivistaaic",
}

# ---------------------------------------------------------------- Fonti di livello B e C
# Non vengono mai lette dal connettore: solo segnalate, con il motivo.
OTHER_SOURCES = [
    {"nome": "Federalismi", "url": "https://federalismi.it", "livello": "B",
     "motivo": "robots.txt blocca molti crawler di AI; articoli protetti L. 633/1941. Solo titolo e link."},
    {"nome": "Consulta Online", "url": "https://www.giurcost.org", "livello": "B",
     "motivo": "robots.txt richiama la riserva dei diritti ex art. 4 dir. UE 2019/790."},
    {"nome": "Giustizia Insieme", "url": "https://www.giustiziainsieme.it", "livello": "B",
     "motivo": "robots.txt non verificabile; ad accesso libero ma da verificare."},
    {"nome": "DPC - Rivista trimestrale", "url": "https://dpc-rivista-trimestrale.criminaljusticenetwork.eu",
     "livello": "B", "motivo": "verifica anti-bot sul sito."},
    {"nome": "InExecutivis", "url": "https://www.inexecutivis.it", "livello": "B (da verificare)",
     "motivo": "contenuto non leggibile in automatico."},
    {"nome": "Jus Civile", "url": "https://www.juscivile.it", "livello": "C",
     "motivo": "robots.txt vieta l'accesso automatico."},
    {"nome": "Diritto Civile Contemporaneo", "url": "https://www.dirittocivilecontemporaneo.com",
     "livello": "C", "motivo": "robots.txt vieta l'accesso automatico."},
    {"nome": "Archivio DPC 2010-2019", "url": "https://www.archiviodpc.dirittopenaleuomo.org",
     "livello": "C", "motivo": "robots.txt vieta l'accesso automatico."},
    {"nome": "DoGi - Dottrina Giuridica (IGSG-CNR)", "url": "http://dati.igsg.cnr.it/dogi",
     "livello": "C", "motivo": "robots.txt vieta l'accesso automatico; banca dati bibliografica gratuita da consultare a mano."},
]
