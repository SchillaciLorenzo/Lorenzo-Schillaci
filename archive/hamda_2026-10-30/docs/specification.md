# HAMDA — Specifica tecnica per lo sviluppo software
**Human Augmentation with Multimodal Digital Assistants**

**Versione:** 0.1 — 22 ottobre 2026  
**Stato:** Prototipo sperimentale in sviluppo  
**Destinatario:** Agente AI di programmazione / Codex  
**Linguaggio principale:** Python

## 1. Obiettivo del progetto

HAMDA è un progetto di ricerca nell'ambito dello Human Factors e dell'Interaction Design, sviluppato per studiare sistemi di assistenza multimodale destinati a operatori impegnati in attività complesse, con particolare attenzione agli astronauti.

L'obiettivo generale è progettare un sistema capace di comunicare informazioni, avvertimenti e indicazioni attraverso diversi canali sensoriali, riducendo il sovraccarico cognitivo e la necessità di consultare costantemente informazioni visive.

Il primo prototipo hardware utilizzerà **16 motori vibranti distribuiti su due piedi (8 per piede)**, controllati attraverso un Raspberry Pi.

Il software dovrà consentire di generare, gestire e modificare segnali aptici, creando una base sperimentale per test futuri con utenti.

### Obiettivi software principali

- Controllare individualmente 16 attuatori vibranti.
- Modificare l'intensità delle vibrazioni.
- Generare sequenze e pattern aptici.
- Gestire attivazioni simultanee e indipendenti.
- Associare eventi e informazioni a specifici pattern.
- Consentire prove manuali e automatizzate.
- Predisporre un'architettura modulare per future integrazioni con sensori, telecamere e altri canali di interazione.

Il software iniziale non deve essere considerato un dispositivo di sicurezza certificato per operazioni astronautiche.

## 2. Hardware e tecnologie

### Decisioni confermate

| Componente | Specifica | Stato |
|---|---|---|
| Computer | Raspberry Pi 4 Model B, 4 GB RAM | Scelto |
| Linguaggio | Python | Scelto |
| Controller PWM | PCA9685, 16 canali | Scelto |
| Driver | Moduli MOSFET logic-level, 2 schede da 8 canali | Scelti |
| Attuatori | 16 coin vibration motors, 8 per piede | Scelti come obiettivo |
| Alimentazione | Powerbank 5 V / 3 A | Scelta progettuale |
| Memoria | microSD da 64 GB | Scelta |
| Cablaggio | Cavi, jumper e connettori JST | Previsti |
| Protezione alimentazione | Condensatori da 1000 µF | Previsti |
| Strumenti di sviluppo | Thonny, Python | Già avviati |

### Vincoli hardware

Il Raspberry Pi non deve alimentare direttamente i 16 motori tramite i GPIO.

Il PCA9685 genera i segnali PWM di controllo, mentre i MOSFET devono gestire la corrente dei motori mediante un circuito adeguato.

L'interfaccia Raspberry Pi–PCA9685 dovrà utilizzare il bus I²C.

Prima di azionare i motori, occorre verificare:

- Modello esatto e piedinatura dei MOSFET.
- Tensione e corrente nominale dei motori.
- Presenza delle protezioni per carichi induttivi.
- Compatibilità elettrica con i segnali a 3,3 V.
- Dimensionamento dell'alimentazione per il carico simultaneo.
- Cablaggio e corretta gestione delle masse.

**Importante:** non considerare lo schema elettronico definitivo finché queste verifiche non sono completate.

## 3. Funzionalità software richieste

### F1 — Controllo individuale dei motori

Il sistema dovrà identificare ciascuno dei 16 motori attraverso un ID univoco.

Si propone la numerazione:

- L1–L8: piede sinistro.
- R1–R8: piede destro.

Per ciascun motore dovranno essere disponibili i seguenti comandi:

- Attivazione.
- Disattivazione.
- Regolazione dell'intensità.
- Attivazione temporizzata.

La corrispondenza fra ID logico, posizione anatomica e canale fisico del PCA9685 dovrà essere configurabile.

### F2 — Regolazione dell'intensità

**Decisione confermata:** l'intensità delle vibrazioni deve essere regolabile.

**Proposta software:** rappresentare l'intensità mediante un valore da 0 a 100, successivamente convertito nel duty cycle PWM appropriato.

- 0 = motore spento.
- 100 = intensità massima ammessa dalla configurazione.

Non assumere che l'intensità percepita cresca linearmente con il duty cycle.

Prevedere limiti configurabili per ogni motore e impedire l'utilizzo di valori fuori intervallo.

### F3 — Pattern aptici

**Proposta di implementazione:** sviluppare un sistema per definire sequenze di vibrazioni.

Pattern iniziali suggeriti:

1. Impulso breve.
2. Impulso lungo.
3. Vibrazione intermittente.
4. Sequenza progressiva tra motori.
5. Attivazione contemporanea di più motori.
6. Pattern direzionale.
7. Segnale di attenzione o pericolo.

Questi pattern sono esempi da sperimentare, non un linguaggio aptico scientificamente validato.

Ogni pattern dovrà poter specificare motori coinvolti, intensità, durata, pause e ripetizioni.

### F4 — Gestione degli eventi

**Proposta:** introdurre un modulo che associ eventi a determinati pattern.

Categorie iniziali suggerite:

- Informazione ordinaria.
- Indicazione direzionale.
- Avvertimento.
- Evento critico.

Il sistema dovrà poter gestire la priorità tra segnali concorrenti.

Il comportamento in caso di sovrapposizione, interruzione o sostituzione dei pattern è ancora da definire.

### F5 — Interfaccia di controllo

**Proposta per la prima versione:** interfaccia a riga di comando (CLI) utilizzabile da Thonny o dal terminale del Raspberry Pi.

Funzioni:

- Selezionare un motore.
- Specificare l'intensità.
- Impostare la durata.
- Attivare un pattern.
- Fermare tutti i motori.
- Eseguire un test diagnostico.

Una dashboard grafica potrà essere sviluppata successivamente, ma non deve bloccare i primi test hardware.

### F6 — Logging sperimentale

**Proposta:** registrare in file CSV o JSON gli eventi principali.

Dati suggeriti:

- Timestamp.
- Motore o gruppo attivato.
- Pattern richiesto.
- Intensità impostata.
- Durata.
- Origine del comando.
- Eventuali errori.

Questo permetterà di confrontare le condizioni sperimentali e riprodurre i test.

## 4. Dati in ingresso

### Ingressi della prima versione

| Input | Tipo | Descrizione |
|---|---|---|
| Motor ID | Stringa / intero | Identificativo del motore |
| Intensity | Numero | Intensità richiesta |
| Duration | Numero | Durata in millisecondi |
| Pattern ID | Stringa | Pattern da eseguire |
| Command | Stringa | Start, stop, test |
| Event | Oggetto | Evento simulato o generato dal software |

I comandi potranno essere inizialmente inseriti manualmente.

### Ingressi futuri — non ancora confermati

- Dati provenienti da una telecamera.
- Eventi generati da algoritmi di computer vision.
- Dati di sensori esterni.
- Coordinate o indicazioni direzionali.
- Informazioni provenienti da altri sistemi di assistenza.
- Comandi di interazione multimodale.

**Non presumere che esistano già algoritmi di riconoscimento visivo, dataset addestrati o API disponibili.**

## 5. Risultati attesi

### Output fisici

- Vibrazione di un singolo motore.
- Vibrazione simultanea di più motori.
- Pattern temporali riproducibili.
- Variazione controllata dell'intensità.
- Disattivazione completa su comando.

### Output software

- Conferma dei comandi eseguiti.
- Segnalazione di errori.
- Stato logico dei motori.
- File di configurazione.
- Log delle attività sperimentali.

Lo stato logico comandato non deve essere confuso con una conferma fisica del movimento del motore, poiché non sono stati definiti sensori di feedback.

### Criteri di accettazione proposti per la versione 1

1. Il software identifica correttamente tutti i 16 canali.
2. Ogni motore può essere comandato singolarmente.
3. Due o più motori possono essere azionati contemporaneamente.
4. È possibile controllare la durata di ogni attivazione.
5. È possibile variare l'intensità nei limiti consentiti.
6. Il comando STOP disattiva tutte le uscite.
7. I pattern configurati possono essere ripetuti.
8. Gli errori software non lasciano intenzionalmente attive le uscite.

I test con carichi reali saranno eseguiti soltanto dopo la verifica elettrica.

## 6. Architettura software proposta

Struttura modulare consigliata:

```text
HAMDA/
│
├── main.py
│
├── config/
│   ├── hardware.json
│   └── patterns.json
│
├── hardware/
│   ├── pca9685_controller.py
│   └── motor_controller.py
│
├── haptics/
│   ├── pattern_engine.py
│   └── event_manager.py
│
├── interfaces/
│   └── cli.py
│
├── logging/
│   └── experiment_logger.py
│
├── tests/
│   ├── test_motor_controller.py
│   └── test_patterns.py
│
├── requirements.txt
└── README.md
```

Questa struttura è una **proposta tecnica**, non una decisione già approvata.

### Responsabilità dei moduli

**Motor Controller:** gestisce motori, canali, intensità e disattivazione.

**PCA9685 Controller:** comunica con il dispositivo fisico tramite I²C.

**Pattern Engine:** genera le sequenze temporali e le vibrazioni coordinate.

**Event Manager:** interpreta gli eventi e seleziona il pattern corrispondente.

**CLI:** consente all'operatore di interagire con il prototipo.

**Experiment Logger:** registra i dati dei test.

### Librerie Python da valutare

- `adafruit-circuitpython-pca9685`
- `adafruit-blinka`
- `pytest`

Le dipendenze e le versioni dovranno essere verificate rispetto al sistema operativo installato sul Raspberry Pi.

## 7. Vincoli progettuali

### Vincoli confermati

- Utilizzare Raspberry Pi 4 come computer principale.
- Utilizzare Python.
- Supportare 16 attuatori.
- Utilizzare il PCA9685.
- Garantire il controllo individuale dell'intensità.
- Mantenere un'architettura estendibile.
- Privilegiare un prototipo trasportabile e alimentato tramite powerbank.
- Progettare il sistema per attività di ricerca e test, non per utilizzo operativo certificato.

### Vincoli di sicurezza software proposti

- Tutti i motori spenti all'avvio.
- Tutti i motori spenti alla chiusura ordinaria.
- Limiti di durata e intensità configurabili.
- Arresto globale tramite comando dedicato.
- Gestione degli errori di comunicazione I²C.
- Nessuna attivazione automatica all'accensione.
- Possibilità di eseguire test simulati senza hardware.

Un comando STOP software non sostituisce un sistema fisico di interruzione dell'alimentazione. La sicurezza in caso di blocco del Raspberry Pi deve essere valutata anche a livello elettronico.

## 8. Decisioni già prese

Sono da trattare come decisioni progettuali attuali:

1. Il sistema si chiama HAMDA.
2. Il progetto riguarda assistenza multimodale e Human Factors.
3. Il primo prototipo utilizza vibrazioni distribuite sui piedi.
4. Il numero previsto è 16 motori, 8 per piede.
5. Il computer è Raspberry Pi 4 Model B.
6. Il software principale sarà scritto in Python.
7. Il PCA9685 gestirà la generazione PWM.
8. Il pilotaggio dei motori richiede driver MOSFET.
9. È necessaria la regolazione dell'intensità.
10. Il prototipo deve poter essere alimentato con una soluzione portatile.

## 9. Proposte da non considerare definitive

Le seguenti idee richiedono validazione progettuale o sperimentale:

- Utilizzare la scala software 0–100 per l'intensità.
- Numerare i motori L1–L8 e R1–R8.
- Definire una libreria di pattern standard.
- Associare priorità agli eventi.
- Utilizzare file JSON per le configurazioni.
- Utilizzare file CSV per le registrazioni.
- Introdurre una CLI per i primi test.
- Sviluppare un'interfaccia grafica in una fase successiva.
- Integrare la computer vision.
- Integrare un canale audio.
- Associare specifiche posizioni anatomiche a particolari segnali.
- Utilizzare sensori aggiuntivi.

## 10. Questioni ancora aperte

### Hardware

- Quali sono le specifiche elettriche esatte dei motori?
- Qual è il modello effettivo dei moduli MOSFET?
- Quale sarà la piedinatura definitiva?
- Come verranno alimentati separatamente o congiuntamente Raspberry Pi e motori?
- Quali protezioni elettriche sono già presenti e quali vanno aggiunte?
- Qual è la corrente massima assorbita con 16 motori attivi?
- Quale sarà la disposizione anatomica definitiva degli attuatori?
- Quale sistema limiterà la durata delle vibrazioni in caso di guasto?

### Software

- Quale versione di Raspberry Pi OS e Python sarà utilizzata?
- Quali frequenze PWM saranno compatibili con i motori reali?
- Quali limiti minimi e massimi di intensità saranno appropriati?
- Quale risoluzione temporale è necessaria per gli esperimenti?
- Come gestire eventi simultanei e priorità?
- Quale sarà il protocollo per eventuali ingressi esterni?
- È necessario un sistema di controllo remoto?
- Come verranno sincronizzati gli eventi con i dati delle sperimentazioni?

### Ricerca e interazione

- Quali pattern risultano distinguibili dagli utilizzatori?
- Quali posizioni anatomiche offrono la percezione più affidabile?
- Come cambiano le prestazioni durante il movimento?
- Come minimizzare l'affaticamento percettivo?
- Quali informazioni devono essere veicolate attraverso il tatto anziché attraverso vista o udito?
- Quali metriche saranno utilizzate per valutare il sistema?

## 11. Piano di sviluppo proposto

**Fase 1 — Fondamenta**

Creare il progetto Python, la configurazione dei canali e una modalità simulata che non richieda hardware.

**Fase 2 — Test del singolo motore**

Realizzare il controllo di un singolo canale PCA9685, dopo la verifica elettrica.

**Fase 3 — Controllo dei 16 motori**

Aggiungere la mappatura dei canali e il controllo indipendente.

**Fase 4 — Pattern aptici**

Implementare sequenze temporizzate, intensità e attivazioni simultanee.

**Fase 5 — Eventi e priorità**

Aggiungere una gestione degli eventi simulati e la logica di selezione dei pattern.

**Fase 6 — Sperimentazione**

Integrare logging, configurazioni e test riproducibili.

**Fase 7 — Estensioni future**

Valutare computer vision, sensori esterni, audio e interazioni multimodali.

## 12. Istruzioni operative per l'agente di programmazione

Sviluppa il progetto secondo le specifiche precedenti.

Mantieni sempre una distinzione tra:

- **CONFIRMED:** requisiti e componenti confermati.
- **PROPOSED:** scelte progettuali suggerite ma modificabili.
- **OPEN:** questioni non ancora risolte.

Non inventare specifiche elettroniche, posizioni anatomiche, frequenze PWM o parametri di sicurezza non verificati.

Inizia realizzando una versione simulata e testabile del controller dei 16 motori. Separa completamente la logica applicativa dalle librerie hardware, in modo da poter sviluppare e testare il programma anche su un computer privo di Raspberry Pi.

Scrivi codice modulare, commentato e comprensibile a una persona che sta imparando Python.

Includi istruzioni dettagliate per installazione, avvio, test e risoluzione degli errori.

Non passare automaticamente alle fasi successive senza aver verificato il funzionamento di quella precedente.

**Primo deliverable richiesto:** un'applicazione Python funzionante in modalità simulata, con 16 motori virtuali, controllo individuale dell'intensità, attivazione temporizzata, stop globale e test automatici di base.