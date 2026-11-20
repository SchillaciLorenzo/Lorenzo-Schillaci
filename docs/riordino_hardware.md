> Documentazione storica del banco PCA9685/DRV. Per la cintura con due ESP32-C3 USB leggere lo [stato attuale](STATO_2026-11-20.md).

# Riordino del banco HAMDA: proposta del 9 novembre 2026

Stato: proposta di supporto e materiali, non ancora costruita o collaudata.
Il riferimento funzionante resta il banco a quattro motori documentato in
quattro_motori_raspberry.md e il relativo archivio del 9 novembre.

## Esigenza e osservazioni

La foto IMG_9175 2.HEIC mostra due DRV molto vicine sulla breadboard,
numerosi cavetti Dupont lunghi e Pi, PCA e convertitore appoggiati sul
tavolo. La foto non permette di verificare ogni contatto o saldatura.
L'utente vuole ridurre l'ingombro della breadboard e preferisce comprare
materiale adatto; al momento della richiesta si trova a casa.

## Soluzione proposta

Preparare a parte una basetta millefori in FR4 a piazzole isolate, con
zoccoli femmina per accogliere le due DRV e collegamenti saldati comuni.
Fissare basetta, Pi, PCA e regolatore a un supporto isolante, con spazio
per spine, ventilazione e uscita ordinata dei cavi. I collegamenti sulla
millefori vengono realizzati con fili saldati: i fori adiacenti non sono
automaticamente collegati fra loro.

Ogni DRV riproduce il circuito gia' funzionante:

- IN2, IN4 e GND collegati localmente al negativo comune.
- VCC e SLEEP collegati localmente al positivo motori circa 3 V.
- IN1 e IN3 ricevono i due comandi dalla PCA.
- OUT1/OUT2 e OUT3/OUT4 arrivano alle due prese per i motori sulla basetta.
- FAULT libero; nessun ponte J1.

I sette collegamenti esterni di ingresso/alimentazione per DRV diventano
quattro: due comandi e una coppia di alimentazione. Le derivazioni dei
positivi e negativi si fanno sulla basetta. I quattro fili delle uscite
motori per DRV restano necessari e vanno raccolti a coppie ed etichettati.

La corrente di alimentazione e ritorno delle DRV va direttamente al
regolatore attraverso la basetta. Il GND della PCA si collega allo stesso
negativo come riferimento. La corrente dei motori non va instradata
attraverso la PCA o il suo cavetto di massa. Pi/PCA mantengono la logica
a 3,3 V; il positivo motori e' quello a circa 3 V; PCA V+ resta libero.

## Materiali suggeriti

| Materiale | Specifica per la ricerca |
| --- | --- |
| Millefori | FR4, passo 2,54 mm, piazzole isolate; confezione con 7x9 e 10x15 cm |
| Zoccoli femmina | Singola fila 1x6, passo 2,54 mm; quattro pezzi per due DRV, confezione con ricambi |
| Pin maschio | Strip singola fila 1x40, passo 2,54 mm, separabile; prese dei segnali e delle uscite motori |
| Morsetto d'ingresso | Due poli, per PCB, passo 5,08 mm; ingresso alimentazione motori |
| Filo per ponticelli | Rame rigido isolato AWG22, circa 0,32 mm2, colori rosso/nero e altri per segnali |
| Filo d'ingresso | Rame flessibile circa 0,5 mm2, rosso e nero, per il piccolo banco corrente |
| Fissaggio | Distanziatori e viti in nylon M2.5 per il Pi; dimensioni degli altri fissaggi da verificare |

Le specifiche sono una lista generica, non prodotti acquistati o annunci
verificati. Selezionare il supporto finale dopo aver disposto i componenti.
Misurare passo e distanza tra le file delle DRV prima di saldare gli
zoccoli; verificare verso e lunghezza dei pin gia' montati e lo spazio
sotto le schede. Non e' ancora definito un disegno foro per foro.
I morsetti scelti devono avere pin che entrino nei fori della millefori.
Il materiale e la sezione del cablaggio non stabiliscono la capacita'
del regolatore; prima di ampliare il carico misurare corrente e tensione.

I connettori bianchi dei motori non sono stati identificati per famiglia
e passo. Si possono riutilizzare i cavetti attuali; non ordinare una
famiglia specifica di connettori assumendo che tutti i bianchi coincidano.

## Sequenza successiva

1. Scegliere e verificare i materiali e la geometria dei pin delle DRV.
2. Disegnare disposizione, orientamento e collegamenti della basetta.
3. Assemblare il supporto a parte e verificare continuita' e assenza di
   collegamenti indesiderati a circuito privo di alimentazione.
4. Trasferire e provare una DRV alla volta, confrontando il risultato
   con il programma funzionante. Spostare i cavetti a Pi e powerbank spenti.
5. Raccogliere e segnare i cavi M1--M4, quindi fissare i componenti e i
   cavi per evitare che la trazione arrivi ai contatti.

Il riordino conserva la funzione elettrica e i comandi del banco attuale.
Il nuovo supporto richiede il suo collaudo prima dell'uso; il successo
della vecchia breadboard non verifica le nuove saldature.
