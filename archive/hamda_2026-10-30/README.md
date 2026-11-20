# HAMDA

**Human Augmentation with Multimodal Digital Assistants**

Questo repository contiene il primo prototipo software di HAMDA: un controller
Python per **16 motori virtuali**, con intensità individuale, attivazioni
temporizzate e arresto globale. Si può sviluppare e provare su un normale
computer, senza Raspberry Pi, PCA9685 o motori collegati.

La versione attuale usa esclusivamente la simulazione. Le uscite mostrate sono
lo **stato virtuale comandato dal software**: non dimostrano che un motore fisico
si stia muovendo.

Se parti da zero, comincia dalla [guida ai primi passi](docs/first_steps.md):
spiega il ruolo dei componenti, cosa fare nell'ordine giusto e come provare il
programma con Thonny prima di collegare i motori.

## Cosa puoi fare

- Identificare i motori `L1`–`L8` e `R1`–`R8`.
- Attivare un motore, un gruppo o tutti i motori per una durata scelta.
- Regolare l'intensità di un motore attivo senza prolungarne la scadenza.
- Spegnere un motore o arrestare tutte le uscite della sessione.
- Controllare lo stato e provare il diagnostico simulato.
- Eseguire i test automatici senza installare librerie esterne.

Pattern aptici, priorità degli eventi, registrazione sperimentale avanzata,
interfaccia grafica e controllo hardware sono sviluppi successivi. La specifica
originale è in [docs/specification.md](docs/specification.md); lo stato delle
decisioni è in [docs/decisions.md](docs/decisions.md).

## Requisiti e installazione

Per questa prima implementazione si propone **Python 3.10 o successivo**.
L'ambiente cloud di sviluppo dispone di Python 3.12. La versione effettiva di
Python e Raspberry Pi OS sul dispositivo rimane da verificare.

La simulazione utilizza solo la libreria standard di Python: non sono necessari
`pytest`, le librerie Adafruit o altre dipendenze da scaricare.

Apri il terminale nella cartella del repository. Nell'ambiente cloud:

```bash
cd /workspace/Lorenzo-Schillaci
python --version
```

Se il tuo sistema espone Python tramite `python3`, usa `python3` al posto di
`python` in tutti gli esempi. Per lavorare con un ambiente virtuale separato,
facoltativamente:

```bash
python -m venv .venv
source .venv/bin/activate
```

Su Windows, l'attivazione in PowerShell è `.venv\Scripts\Activate.ps1`.
Non è richiesta l'installazione di pacchetti per eseguire il progetto.

## Avvio della sessione interattiva

```bash
python main.py
```

Un punto di ingresso equivalente è:

```bash
python -m hamda
```

Questi comandi aprono una shell di HAMDA. I comandi successivi vanno inseriti
nel prompt dell'applicazione. Tutti i motori iniziano spenti; il semplice avvio
non attiva alcun canale.

### Primo esempio

```text
status
on L1 50 500
status
```

Il comando `on` richiede, nell'ordine, motore, intensità e durata in
millisecondi. Qui `L1` viene comandato al 50% per 500 ms, poi torna spento
automaticamente. La shell resta disponibile mentre il timer scorre.

Per vedere un'attivazione più lunga e modificarla durante l'esecuzione:

```text
on L1 30 10000
set L1 40
status
off L1
```

`set` modifica un motore già attivo e conserva la scadenza originaria. Per
avviare un motore spento usa `on`. Il valore zero spegne l'uscita.

### Gruppi e arresto

```text
on L1,R1 30 1000
on all 20 200
stop
status
quit
```

Una lista separata da virgole seleziona più motori; `all` li seleziona tutti.
Ogni motore mantiene il proprio stato e la propria temporizzazione. `stop`
annulla le attivazioni in corso e comanda a zero tutte le uscite della sessione.
`quit`, fine input ed eventuale interruzione da tastiera chiudono la sessione
tentando di spegnere tutte le uscite.

### Riferimento dei comandi

| Comando | Esempio | Effetto |
| --- | --- | --- |
| `status` | `status` | Mostra i 16 motori e lo stato virtuale corrente. |
| `on` | `on R3 25 750` | Imposta intensità e durata di un motore. |
| `on` con gruppo | `on L1,R1 30 1000` | Comanda insieme i motori selezionati. |
| `on all` | `on all 20 200` | Comanda tutti i 16 motori. |
| `set` | `set R3 40` | Cambia l'intensità di un motore attivo. |
| `off` | `off R3` | Spegne il motore selezionato. |
| `off` con gruppo | `off L1,R1` | Spegne i motori selezionati. |
| `stop` | `stop` | Spegne tutte le uscite di questa sessione. |
| `test` | `test` | Esegue il diagnostico simulato. |
| `help` | `help` | Mostra l'aiuto della shell. |
| `quit` | `quit` | Spegne le uscite e termina. |

## Comandi singoli dal terminale

Puoi eseguire un comando senza aprire la shell:

```bash
python main.py status
python main.py on L1 50 500
python main.py test
python main.py --help
```

Nel secondo esempio il processo attende la scadenza dei 500 ms e poi chiude.
Ogni invocazione crea un controller simulato indipendente: `python main.py stop`
**non arresta una shell HAMDA già aperta in un altro processo**. Per modificare
o interrompere le attivazioni di una sessione, usa i comandi dentro quella
stessa shell. Questa versione non contiene un servizio di controllo remoto.

Per utilizzare Thonny, apri `main.py` dalla cartella del progetto ed eseguilo.
I comandi interattivi vanno inseriti nella shell di Thonny quando compare il
prompt di HAMDA.

## Configurazione

Il file [config/hardware.json](config/hardware.json) definisce la mappa dei
motori e i limiti della simulazione. Puoi selezionare un file alternativo:

```bash
python main.py --config config/hardware.json
```

La mappatura iniziale proposta è:

| ID logici | Canali virtuali | Posizione anatomica |
| --- | --- | --- |
| `L1`–`L8` | `0`–`7` | Non definita (`null`). |
| `R1`–`R8` | `8`–`15` | Non definita (`null`). |

L'intensità richiesta usa una scala software da 0 a 100 e deve rispettare il
`max_intensity` del singolo motore. La configurazione iniziale usa 100 per tutti
i motori e una durata massima globale `max_duration_ms` di 60000 ms. Sono
**PROPOSED: limiti di esempio per la simulazione**, modificabili nel file; non
sono valori di sicurezza verificati per attuatori reali.

Il duty cycle visualizzato descrive una conversione numerica della richiesta
software. Non si assume una relazione lineare con l'intensità percepita. Non
sono configurati frequenze PWM, pin o parametri elettrici non ancora verificati.
Un errore nella mappatura o nei limiti impedisce l'avvio del controller invece
di usare una configurazione parziale.

## Test automatici

Dalla cartella del progetto:

```bash
python -m unittest discover -s tests -v
```

La suite verifica il comportamento del software simulato, inclusi controllo
individuale, limiti, timer e arresto. Il diagnostico `test` disponibile nella
CLI è una prova manuale aggiuntiva e non sostituisce la suite automatica.

I timer usano il tempo monotono del computer per evitare che una modifica
dell'orologio civile alteri le scadenze. Python e il sistema operativo non
forniscono qui garanzie di esecuzione in tempo reale: la precisione richiesta
dagli esperimenti rimane da definire e misurare.

I test sul cloud non validano l'elettronica, la percezione aptica, la precisione
temporale sul Raspberry Pi o la sicurezza del dispositivo. Prima di passare
alla fase hardware occorre verificare la fase simulata, completare le verifiche
elettriche della specifica e confermare i parametri reali necessari.

## Organizzazione del codice

- `main.py` e `hamda/__main__.py`: punti di ingresso.
- `hamda/cli.py`: comandi del terminale e shell interattiva.
- `hamda/config.py`: lettura e controllo della configurazione.
- `hamda/controller.py`: stato dei motori, intensità, timer e arresto.
- `hamda/hardware/`: contratto delle uscite e backend simulato.
- `config/hardware.json`: mappatura configurabile dei 16 canali.
- `tests/`: test automatici della versione simulata.
- `docs/`: specifica originale e decisioni progettuali.

La logica del controller comunica con un backend separato. In futuro un backend
PCA9685 potrà implementare quel contratto senza portare dipendenze hardware nei
test della logica applicativa. Quel backend non è implementato in questa fase.

## Risoluzione degli errori

| Problema | Verifica o azione |
| --- | --- |
| `python` non viene trovato | Prova `python3` e verifica la versione installata. |
| Non viene trovato `main.py` o il modulo `hamda` | Esegui il comando dalla cartella del repository. |
| La configurazione non viene letta | Verifica il percorso passato a `--config` e la sintassi JSON. |
| Un ID motore viene rifiutato | Usa un ID configurato, ad esempio `L1`; controlla la mappatura. |
| Intensità o durata vengono rifiutate | Rispetta intervalli numerici e limiti del file di configurazione. |
| `set` su un motore spento fallisce | Avvialo prima con `on`, indicando una durata. |
| Non senti vibrazioni | Questa versione è solo simulata e non aziona hardware. |
| STOP da un altro terminale non cambia lo stato | Inserisci `stop` nella shell che ha creato le attivazioni. |

All'avvio e alla chiusura il controller comanda le uscite spente. In caso di
errore del backend tenta uno spegnimento globale. Un comando software non può
garantire lo spegnimento fisico con bus guasto, alimentazione non controllata o
processo terminato forzatamente. Le protezioni e l'interruzione fisica
dell'alimentazione appartengono alla progettazione elettronica ancora aperta.

HAMDA rimane un prototipo di ricerca, senza certificazione per impiego operativo
astronautico.
