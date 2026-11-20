> Documentazione storica del banco PCA9685/DRV. Per la cintura con due ESP32-C3 USB leggere lo [stato attuale](STATO_2026-11-20.md).

# HAMDA: preparazione della prova con due motori

Stato al 5 novembre 2026: il primo motore ha superato la prova reale.
L'utente ha confermato di aver saldato il secondo motore al cavetto
femmina, inserito il connettore su OUT3/OUT4 e completato il nuovo comando
PCA uscita 1 verso IN3, dopo aver rimosso il precedente collegamento IN3
a massa. Non e' stato comunicato un valore di resistenza del secondo
motore. Il programma e' stato installato sul Raspberry e il comando `off`
ha confermato i due registri di spegnimento. `secondo` termina senza errori
ma l'utente non osserva vibrazione. L'utente ha poi provato motori e
cavetti su OUT1/OUT2 con `primo`, dichiarandoli funzionanti; il log allegato
conferma ripetute esecuzioni terminate senza errori. Questo non verifica
il ponte OUT3/OUT4 ne' il suo comando da PCA uscita 1 verso IN3/IN4.
La prova reale dei due motori indipendenti resta da completare.
I collegamenti sotto riportano le istruzioni seguite; non sono stati
verificati con nuove fotografie.

Aggiornamento prima del ripristino: le foto IMG_9109/9110 hanno fatto
individuare IN3 libero, poi confermato dall'utente. Dopo aver inserito il
cavetto su IN3, l'utente ha descritto i due attacchi PCA uscita 1 invertiti:
IN3 verso il pin nero e pin giallo verso il negativo della breadboard.
Ha confermato di averli scambiati secondo le istruzioni: giallo 1 verso
IN3, nero 1 verso negativo. Non e' ancora seguita una prova riuscita del
secondo motore, perche' l'accesso USB/SSH e' diventato indisponibile.
Non considerare collaudata l'uscita 1 della PCA.

Il Mac ha rilevato a tratti il gadget USB e la sua interfaccia en7, MAC
02:48:41:4d:44:02. Inizialmente il traffico verso 10.55.0.2 passava per
Wi-Fi en0; l'assegnazione temporanea con ifconfig ha ripristinato il
percorso en7, ma il ping e' rimasto senza risposta. Successivamente en7
risultava inattiva e senza indirizzi. L'utente ha riferito attivazione
breve durante l'avvio e successiva inattivita'. La causa non e' stata
accertata. Il 5 novembre l'utente ha autorizzato la reinstallazione della
microSD e la ricreazione dei programmi, mantenendo i sorgenti precedenti
come riferimento.

## Collegamenti previsti

Spegnere il Raspberry e scollegare fisicamente sia la sua USB sia la USB
del powerbank dei motori prima di modificare i fili.

- Primo motore: connettore gia' presente su DRV OUT1 e OUT2.
- Secondo motore: connettore femmina su DRV OUT3 e OUT4; rosso su OUT3,
  nero su OUT4. Il contatto FAULT, serigrafato ULT nella foto, resta libero.
  Non usare gli ultimi due pin della fila: uno e' FAULT.
- Primo comando invariato: pin giallo PCA uscita 0 verso DRV IN1;
  DRV IN2 a GND.
- Secondo comando: rimuovere il vecchio collegamento IN3 verso la fila
  negativa della breadboard. Collegare con un cavetto femmina-femmina il
  pin giallo PCA uscita 1 a DRV IN3. Lasciare DRV IN4 a GND.
- Il GND comune e' gia' presente; non serve un secondo ponticello di massa.

Con la PCA orientata con morsetto verde in alto, condensatore in alto a
sinistra e striscia colorata in basso, l'uscita 0 e' il primo gruppo di
tre pin a sinistra. L'uscita 1 e' il gruppo immediatamente a destra.
Il pin giallo e' quello interno, vicino al circuito integrato. I colori
descrivono la plastica sulla scheda, non il colore dei cavetti.

I pin rossi V+ e il morsetto verde PCA restano liberi. Alimentazione motori
circa 3 V dal convertitore; Raspberry alimentato dal Mac tramite USB.
Riferimento per i collegamenti gia' verificati: `primo_motore_raspberry.md`.

## Programma preparato, da installare sul Raspberry

Tenere `tools/hamda_due_motori.py` e `tools/hamda_primo_motore.py` nella
stessa cartella: il nuovo programma importa quello del primo motore.
La presenza dei file nel workspace cloud non li installa sul Raspberry.
Il primo programma e' rimasto invariato.

Con collegamenti controllati, Raspberry acceso e powerbank motori ancora
scollegato, il comando iniziale nella sessione SSH del Raspberry e':

```bash
python3 ~/hamda_due_motori.py off
```

Dopo la conferma di spegnimento, collegare il powerbank: entrambi i motori
devono restare fermi. Provare poi un comando alla volta, controllando
l'arresto di entrambi dopo ciascuna prova:

```bash
python3 ~/hamda_due_motori.py primo
python3 ~/hamda_due_motori.py secondo
python3 ~/hamda_due_motori.py insieme
```

`primo` attiva solo il motore su OUT1/OUT2; `secondo` solo quello su
OUT3/OUT4; `insieme` entrambi. L'impulso impostato dura 0,25 secondi.
Questa prova usa acceso/spento e non regola ancora l'intensita'.
Al termine scollegare il powerbank dei motori.

Il programma legge la conferma FULL_OFF per entrambi i canali e usa lo
stesso lock del primo programma. Le prove sono sorvegliate: errori I2C,
SIGKILL o blocchi del sistema possono impedire lo spegnimento software.
Tenere disponibile la disconnessione fisica del powerbank.

## Verifica nel workspace

Superati 12 test con bus simulato: sei del primo programma e sei del
secondo. Le nuove prove verificano selezione indipendente dei motori,
accensione di entrambi, arresto dopo interruzione o conferma I2C persa,
rilevazione di un arresto non confermato e rifiuto dei canali non ammessi.

```bash
python3 -m unittest discover -s tests
```

Questi risultati non sostituiscono la prova sul secondo motore reale.
