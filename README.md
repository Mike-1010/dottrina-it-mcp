# dottrina-it-mcp (v0.1.0)

Connettore MCP per la **dottrina giuridica italiana ad accesso libero**: ricerca e lettura
di saggi, note a sentenza e commenti, nel rispetto di licenze, paywall e robots.txt.

## Fonti (livello A: lettura su richiesta consentita)

| Rivista | Come viene cercata | Limiti rispettati |
|---|---|---|
| Sistema Penale | indice da sitemap + ultimi 150 contributi (con data e autori) | versione stampabile `?out=print`; licenza CC BY-NC-ND 4.0 |
| Questione Giustizia | indice dalle ultime 3 pagine di 7 categorie | nessuno dichiarato |
| Archivio Penale | indice degli ultimi 12 fascicoli web + 4 sezioni di giurisprudenza | solo contributi marcati "open access"; mai i link "a pagamento" |
| Judicium | API REST di WordPress, solo categoria "Aggiornamenti" (id 60) | i saggi dei fascicoli (abbonamento) non vengono mai letti |
| Persona e Mercato | indice dai post dei numeri (elenco dei PDF) | riproduzione solo con indicazione della fonte |
| Rivista AIC | ricerca del sito | 10 secondi tra le richieste (Crawl-delay) |

Le fonti di livello B e C (Federalismi, Consulta Online, Giustizia Insieme, DPC trimestrale,
InExecutivis, Jus Civile, Diritto Civile Contemporaneo, Archivio DPC, DoGi) **non vengono
lette**: `leggi_contributo` restituisce solo il motivo e invita a segnalare il link.

## Strumenti

- `cerca_dottrina(query, fonti, autore, anno, max_risultati)`: ricerca su titolo, autori e
  indirizzo; ogni risposta indica la copertura di ciascuna rivista.
- `commenti_a_sentenza(estremi, fonti)`: note e commenti che citano una decisione nel titolo
  o nell'indirizzo (corrispondenza "forte" = numero e anno, "possibile" = solo numero).
- `leggi_contributo(url, da_carattere, max_caratteri)`: testo di una pagina HTML o di un PDF,
  a blocchi (`prossimo_da_carattere`).
- `ultime_pubblicazioni(fonti, n)`: novità per rivista.
- `elenca_fonti()`: fonti, livelli, licenze, copertura attuale.

Gli indici si costruiscono in background alla prima ricerca (circa un minuto) e si
aggiornano ogni 6 ore. Su Render free il servizio si addormenta dopo 15 minuti di inattività:
al risveglio gli indici si ricostruiscono.

## Regole di accesso (sempre attive)

- Solo i domini delle sei riviste; robots.txt letto per ogni sito e rispettato a runtime.
- Almeno 1,5 secondi tra due richieste allo stesso sito (10 secondi per Rivista AIC).
- Cache in memoria di 15 minuti; nessun testo salvato su disco.
- User-Agent onesto, configurabile con `DOTTRINA_UA`.

## Pubblicazione su Render

- Tipo di servizio: **Web Service**, runtime Python.
- Build command: `pip install -r requirements.txt`
- Start command: `python server.py`
- Variabili d'ambiente:
  - `MCP_PATH` = un percorso segreto, es. `/x7k2p9-dottrina/mcp` (senza, il server è pubblico);
  - `PYTHON_VERSION` = `3.12.7` (consigliato);
  - facoltative: `DOTTRINA_UA` (User-Agent con un contatto), `SP_LIST_PAGES`, `QG_PAGES`,
    `AP_FASCICOLI` (profondità degli indici).
- Collegamento a Claude: Impostazioni → Connettori → Aggiungi connettore personalizzato →
  URL completo `https://<nome-servizio>.onrender.com<MCP_PATH>`.

## Prova locale

    pip install -r requirements.txt
    python server.py --probe "interrogatorio preventivo"
    python server.py --leggi https://www.sistemapenale.it/it/scheda/...
    python tests/test_offline.py        # collaudo offline (richiede anche reportlab)

## Note di manutenzione

Verifiche dei siti del 04/11/2026 (dettagli e metodo in `config.py`). I parser riconoscono
gli elementi dalla forma degli URL, non dalle classi CSS. Ricontrollare robots.txt e termini
d'uso ogni sei mesi o dopo un cambio di grafica di una rivista.
