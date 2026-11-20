# HAMDA — Consegna del progetto a un'altra chat Codex

Aggiornato al 30 ottobre 2026. Questo documento riassume le richieste dell'utente,
le quantità dichiarate e il lavoro software già svolto. La nuova chat deve
verificare i file allegati: non ha automaticamente accesso ai percorsi o alle
conversazioni della chat precedente.

## Richiesta all'agente

Aiutami a completare HAMDA (Human Augmentation with Multimodal Digital Assistants),
un prototipo di ricerca per comunicare informazioni mediante vibrazioni sui piedi.
Il linguaggio principale è Python. Sono un principiante assoluto: guidami in
italiano con parole semplici, un'operazione concreta alla volta. Quando serve
una mia informazione, chiedimi una cosa per volta; continua nel frattempo lo
sviluppo software che non dipende da quella risposta.

La prima specifica prevedeva 16 motori, 8 per piede. Abbiamo discusso una possibile
espansione a 32 motori comandabili INDIPENDENTEMENTE, non 16 coppie sincronizzate.
Il numero finale di motori da montare non è ancora deciso. Possederne 50 non
significa doverli usare tutti. Non assumere una disposizione anatomica definitiva
né un significato dei pattern scientificamente validato.

## Inventario: quantità dichiarate dall'utente

| Componente | Quantità fisica dichiarata | Cosa resta da verificare |
| --- | --- | --- |
| Motori vibranti | 50 motori singoli | Tipo di attuatore, modello, tensione e corrente nominale/di avvio. |
| Schede PCA9685 | 4 schede | Modello preciso, configurazione e indirizzi I²C delle schede. |
| Moduli chiamati DM0018x8 | 12 moduli | Identificazione esatta, funzione, ingressi, numero di canali e limiti elettrici. |

IMPORTANTE: non identificare automaticamente DM0018x8 come DRV8833 e non dedurre
8 canali dalla sigla. In una foto precedente la confezione riporta DRV8833-6 e
ASIN B0DHRFRG6X, ma la relazione con i 12 DM0018x8 è ancora da chiarire. Il conteggio
di 12 DRV8833 e la capacità di 24 motori, comunicati in precedenza, sono stati
ritirati. Non contare i DRV8833 come un ulteriore gruppo certo di schede.

Sono stati indicati anche un powerbank e convertitori MP1584EN. Le quantità
fisiche totali non sono state comunicate. La confezione MP1584EN è descritta nel
titolo come da 6 pezzi, e la foto DRV8833 indica una confezione da 6: questo NON
stabilisce il numero di confezioni acquistate o il totale posseduto.

Raspberry Pi 4 Model B 4 GB, microSD 64 GB, cavi/jumper/JST e condensatori da
1000 microfarad compaiono nella specifica iniziale come componenti previsti.
Non sono ancora stati riconosciuti e conteggiati individualmente nell'inventario.
Non è noto se il Raspberry sia già configurato o quale sistema operativo utilizzi.

## Intera lista della spesa fornita dall'utente

L'utente dichiara di aver acquistato e avere sul tavolo TUTTE le seguenti 21 voci.
Mantieni lo stesso ordine. "Da identificare" riguarda il nome del prodotto,
non la sua assenza. Non inventare nomi o specifiche a partire dagli ASIN.
PCA9685 e DM0018x8 potrebbero corrispondere a voci non ancora identificate:
non sommarli automaticamente come ulteriori acquisti distinti.

| N. | Identificazione disponibile | Totale pezzi dichiarato | Link |
| --- | --- | --- | --- |
| 1 | Powerbank; modello e uscite da verificare | Da confermare | https://www.amazon.de/dp/B0GSY5CXFF |
| 2 | Da identificare | Da confermare | https://www.amazon.de/dp/B0GY3CM4KY |
| 3 | Da identificare | Da confermare | https://www.amazon.de/dp/B0CMQBD1C3 |
| 4 | Da identificare | Da confermare | https://www.amazon.de/dp/B0DH2H1SKL |
| 5 | Da identificare | Da confermare | https://www.amazon.de/dp/B0F327WFRC |
| 6 | Convertitori MP1584EN step-down | Da confermare | https://www.amazon.de/dp/B0B92WYRR4 |
| 7 | Driver per motori DRV8833, modello commerciale DRV8833-6 | Da confermare | https://www.amazon.de/dp/B0DHRFRG6X |
| 8 | Da identificare | Da confermare | https://www.amazon.de/dp/B07Y9PTY12 |
| 9 | Da identificare | Da confermare | https://www.amazon.de/dp/B09F9J7ZXV |
| 10 | Da identificare | Da confermare | https://www.amazon.de/dp/B0G8LX3JFM |
| 11 | Da identificare | Da confermare | https://www.amazon.de/dp/B0DH2B36G5 |
| 12 | Da identificare | Da confermare | https://www.amazon.de/dp/B0FP4J6NH1 |
| 13 | Da identificare | Da confermare | https://www.amazon.de/dp/B0D8TG5X2B |
| 14 | Da identificare | Da confermare | https://www.amazon.de/dp/B0BPPBLZ34 |
| 15 | Da identificare | Da confermare | https://www.amazon.de/dp/B0F7HFQ4YJ |
| 16 | Da identificare | Da confermare | https://www.amazon.de/dp/B0FKXZZHPW |
| 17 | Da identificare | Da confermare | https://www.amazon.de/dp/B087785H1J |
| 18 | Da identificare | Da confermare | https://www.amazon.de/dp/B0DJ5CHQ33 |
| 19 | Da identificare | Da confermare | https://www.amazon.de/dp/B0FS772W77 |
| 20 | Da identificare | Da confermare | https://www.amazon.de/dp/B0FB8V2FDY |
| 21 | Motori vibranti; modello e caratteristiche da verificare | 50 | https://www.amazon.de/dp/B0C7PFN8H4 |

Ulteriore link PCA9685 fornito prima della lista: https://amzn.eu/d/07x1NT6M

Le pagine Amazon sono risultate inaccessibili nell'ambiente precedente.
Powerbank e motori sono associati ai link dalle dichiarazioni dell'utente;
MP1584EN dal titolo incollato; DRV8833 dalla foto. Per le altre 17 voci manca
ancora un'identificazione. Se hai accesso web, prova a leggere le pagine e usa
fonti affidabili; un link irraggiungibile non giustifica una specifica inventata.
Se l'accesso rimane bloccato, richiedi titoli o foto leggibili in modo semplice.

## Codice già realizzato: riusalo

Esiste già la versione 0.1.0 funzionante in simulazione, con:

- 16 motori virtuali L1–L8 e R1–R8, mappatura configurabile sui canali 0–15.
- Controllo individuale e di gruppi, intensità, durata e STOP globale.
- Timer indipendenti basati su tempo monotono; modificare l'intensità non prolunga
  la scadenza, mentre una nuova attivazione sostituisce il comando precedente.
- Stato spento all'avvio e chiusura ordinaria con tentativo di spegnimento globale.
- Gestione di guasti del backend, inclusi quelli nei timer e nello shutdown.
- CLI e shell interattiva, avviabili con main.py o python -m hamda.
- Backend simulato separato dalla logica; nessun driver fisico PCA9685/DM0018x8
  implementato e nessuna libreria Raspberry Pi necessaria per la simulazione.
- Nessuna dipendenza esterna per esecuzione e test. Sintassi Python 3.10+;
  esecuzione verificata con Python 3.12.14, senza verifica sul Raspberry reale.
- 49 test automatici superati alla verifica del primo deliverable e del pacchetto
  precedente: rieseguili nell'ambiente corrente e riporta il risultato effettivo.

La scala 0–100, il limite iniziale 100 e la durata massima iniziale 60000 ms
sono convenzioni ed esempi della SIMULAZIONE, non parametri elettrici sicuri o
calibrazioni della vibrazione percepita.

File principali: main.py, hamda/config.py, hamda/controller.py,
hamda/hardware/base.py, hamda/hardware/simulated.py, hamda/cli.py,
config/hardware.json e tests/.

Leggi README.md, docs/specification.md (specifica originale completa),
docs/decisions.md, docs/hardware_inventory.md, docs/purchased_components.md,
docs/purchased_components.csv e docs/first_steps.md. Per inventario e quantità
usa le precisazioni più recenti riportate qui e nell'inventario.

Il codice scritto nella chat precedente era nel checkout locale e senza commit;
non è stato inviato su GitHub dall'assistente. Usa il pacchetto allegato per
questa implementazione: non presumere che un clone del remoto la contenga.
Usa il checkout esistente quando disponibile. Ogni task cloud è già isolato:
non creare un Git worktree salvo richiesta esplicita dell'utente.

## Come iniziare a lavorare

Estrai il pacchetto: la cartella principale si chiama HAMDA. Da quella cartella:

    python3 -m unittest discover -s tests -v
    python3 main.py test
    python3 main.py

Nel prompt HAMDA puoi provare, in sola simulazione:

    on L1,R1 40 10000
    set L1 60
    status
    stop
    quit

Ogni processo contiene una simulazione propria. STOP da un'altra invocazione
non controlla una shell già aperta: nessun server remoto è stato implementato.

## Sviluppo richiesto e ordine di lavoro

1. Ispeziona il progetto e verifica la versione simulata già esistente.
2. Prepara una struttura configurabile che possa mantenere il profilo da 16 e
   supportare un profilo simulato da 32 motori indipendenti. Distingui scheda e
   canale, valida i duplicati, estendi backend, CLI, diagnostico e test. L'uso
   fisico di 32 motori resta subordinato alla verifica dei componenti.
3. Aggiungi progressivamente pattern (impulsi, pause, ripetizioni, sequenze e
   gruppi simultanei), eventi simulati e logging degli esperimenti. Per priorità,
   interruzioni e sovrapposizioni scegli una politica esplicita, documentata come
   PROPOSED e verificata con test, senza attribuire ai pattern una validazione
   scientifica o un significato di sicurezza operativo.
4. Per hardware reale identifica prima i DM0018x8 e i motori. Prepara il backend
   fisico per i componenti effettivi soltanto quando le informazioni necessarie
   sono disponibili; continua nel frattempo la logica e i test simulati.
5. Dopo la verifica elettrica, guida una prova da banco su un solo motore, poi
   due con comandi diversi, poi il gruppo previsto. Verifica ogni fase prima di
   proseguire e fornisci istruzioni adatte a un principiante.

Mantieni separati CONFIRMED (requisiti/dati confermati), PROPOSED (scelte attuali
modificabili) e OPEN (informazioni mancanti). Consegna codice modulare, spiegazioni,
configurazioni, istruzioni di avvio e test riproducibili; riporta cosa hai davvero
eseguito e cosa richiede una prova fisica.

## Limiti da rispettare

- Nessuna frequenza PWM, piedinatura, tensione dei motori o corrente disponibile
  è stata verificata. Non fissarle per supposizione. Gli indirizzi I²C effettivi
  devono essere verificati; più PCA9685 sullo stesso bus richiedono indirizzi distinti.
- Quattro PCA9685 offrono 64 segnali PWM potenziali, non la prova che sia possibile
  alimentare 64 motori. Due possono bastare per 32 motori unidirezionali con una
  specifica architettura di ingresso, ma questa non identifica o valida i DM0018x8.
- Il PCA9685 produce comandi; Raspberry e suoi GPIO non alimentano direttamente
  i motori. Il circuito di potenza e gli eventuali convertitori vanno verificati.
- Non dare per acquisita l'uscita del powerbank o quella di un MP1584EN regolabile.
  Le misure fisiche richiedono uno strumento adatto e qualcuno sul posto.
- STOP ed errori devono tentare lo spegnimento di tutte le uscite. Un guasto del
  bus o un blocco del computer non consente una garanzia fisica di spegnimento;
  lo stato comandato non è un feedback sul movimento reale.
- Non assumere computer vision, sensori, dataset, servizi o API già disponibili.
  Queste restano estensioni future.
- HAMDA è un prototipo sperimentale di ricerca, non un sistema certificato per
  uso astronautico operativo.

Nel pacchetto di passaggio è inclusa, se disponibile, la precedente foto
IMG_8943.HEIC sotto docs/attachments/. È la foto con etichetta DRV8833,
non una nuova identificazione fotografica dei DM0018x8.
