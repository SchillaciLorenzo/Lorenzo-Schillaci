> Documentazione storica del banco PCA9685/DRV. Per la cintura con due ESP32-C3 USB leggere lo [stato attuale](STATO_2026-11-20.md).

# HAMDA: primo motore, prova al banco

Questo documento descrive il prototipo a un motore delle sessioni del
4 e 5 novembre 2026. Non descrive il controller HAMDA completo.

## Verifiche effettuate sul banco

- Raspberry Pi 4 Model B, Raspberry Pi OS 64 bit, Python 3.13.5.
- Utente Raspberry `lorenzoschillaci`, hostname `HAMDA`.
- Collegamento USB dati dal Mac Intel, alimentazione del Raspberry dallo
  stesso cavo. Interfaccia Mac `Raspberry Pi USB Gadget`, dispositivo `en7`.
- IP Mac `10.55.0.1/24`, IP Raspberry `10.55.0.2/24`. Ping riuscito e SSH
  funzionante. La configurazione non richiede il Wi-Fi aziendale o un hotspot.
- I2C abilitato con `sudo raspi-config nonint do_i2c 0`, seguito da spegnimento
  e successivo avvio. L'utente appartiene al gruppo `i2c`.
- Una sola PCA9685 HW-170 collegata. `i2cdetect -y 1` ha rilevato `40` e `70`;
  `0x70` corrisponde all'indirizzo All Call della PCA, non a una seconda scheda.
- Motore a disco nominale 3 V. Il venditore riporta valori di corrente e
  potenza incoerenti: non considerarli specifiche affidabili. La resistenza
  misurata e confermata dall'utente e' 30,8 ohm.
- Convertitore verde HW133A: uscita regolata e misurata dall'utente a circa
  3 V; precedente misura sul driver 3,012 V. Motore funzionante nella prova
  diretta e nella prova manuale attraverso la DRV8833.
- Nella prova manuale, IN1 alto ha attivato il motore e IN1 a GND lo ha fermato.
- Il 5 novembre la lettura del registro OFF_H del canale 0 ha restituito
  `0x10`. Il programma Python installato sul Raspberry ha poi confermato
  `PCA: tutte le uscite impostate spente.`
- La prova reale con `python3 ~/hamda_primo_motore.py pulse` e' riuscita:
  l'utente ha osservato la vibrazione e ha confermato separatamente che il
  motore si e' fermato da solo, prima di scollegare la USB del powerbank.
  Il tempo impostato dal software e' 0,25 s; non e' stata misurata la durata
  meccanica effettiva della vibrazione.

## Cablaggio previsto per questa prova

Tutte le modifiche fisiche vanno eseguite senza alimentazione. Scollegare
entrambe le sorgenti: USB Raspberry e USB del convertitore del motore.

| Origine | Destinazione |
| --- | --- |
| Raspberry pin fisico 1, 3,3 V | PCA VCC |
| Raspberry pin fisico 3, SDA | PCA SDA |
| Raspberry pin fisico 5, SCL | PCA SCL |
| Raspberry pin fisico 6, GND | PCA GND |
| PCA uscita 0, pin giallo PWM | DRV8833 IN1 |
| PCA uscita 0, pin nero GND | Fila negativa della breadboard, comune a DRV GND e VOUT- |
| Convertitore VOUT+, circa 3 V | DRV VCC, attraverso la breadboard |
| Convertitore VOUT- | DRV GND, attraverso la breadboard |
| Fila negativa della breadboard | DRV IN2, IN3 e IN4 |
| Fila positiva a circa 3 V della breadboard | Pin SLEEP della DRV, serigrafato EEP |
| DRV OUT1 e OUT2 | Motore, attraverso la prolunga |

Il cavetto maschio-femmina che prima univa IN1 alla fila negativa e' stato
riutilizzato per GND comune: l'estremita' maschio resta nella fila negativa;
la femmina e' stata spostata da IN1 al pin nero dell'uscita 0 della PCA.
Un nuovo femmina-femmina collega poi il pin giallo dell'uscita 0 a IN1.
Il collegamento sul pin nero PCA e' stato fotografato e verificato; quello
del comando IN1 e' stato dichiarato completato dall'utente.

Sulla PCA, morsetto verde e pin rossi V+ restano liberi. Le alimentazioni
positive 3,3 V logica e circa 3 V motore non si uniscono. Non ponticellare J1
sulla DRV. Il secondo ponte della DRV non e' collegato a un motore.

I colori dei cavetti non definiscono la loro funzione. Giallo, rosso e nero
nelle istruzioni dell'uscita PCA indicano il colore della base di plastica
dei pin sulla scheda.

## Programma di prova

`tools/hamda_primo_motore.py` usa solo la libreria standard Python e il
dispositivo Linux `/dev/i2c-1`. Nessuna installazione di pacchetti richiesta.
Indirizzo fisso `0x40`, uscita 0, impulso fisso di 0,25 secondi.

Per il primo test il comando e' completamente acceso/spento: non modifica
la frequenza PWM e non regola ancora l'intensita'. Il motore riceve i 3 V
del convertitore attraverso il ponte DRV; la PCA fornisce solo il comando.

Sequenza operativa:

1. Raspberry/PCA alimentati dal Mac, powerbank del motore scollegato.
2. Eseguire `python3 hamda_primo_motore.py off` sul Raspberry e controllare
   il messaggio di uscite impostate spente.
3. Collegare il powerbank del motore. Il motore deve restare fermo.
4. Eseguire `python3 hamda_primo_motore.py pulse` e verificare che il motore
   vibri brevemente e poi si fermi.
5. Al termine della prova scollegare il powerbank del motore.

Il codice forza prima FULL_OFF su tutte le 16 uscite e poi configura
l'uscita non invertita. L'impulso usa FULL_ON sul solo canale 0. Un blocco
`finally` forza nuovamente tutte le uscite spente, con lettura di conferma
del bit FULL_OFF del canale 0. SIGINT, SIGTERM e SIGHUP attivano la stessa
sequenza di uscita; un lock impedisce due esecuzioni contemporanee di
questo programma.

La verifica del registro non misura la corrente del motore. Un guasto I2C,
SIGKILL, un blocco del sistema o un altro programma che scrive nella PCA
possono lasciare attivo un comando. Questo test deve essere sorvegliato e
resta necessario poter scollegare fisicamente il powerbank del motore.
Non e' implementato un arresto indipendente dall'esecuzione del software.

## Stato delle verifiche del nuovo programma

Sei test con bus simulato superati: spegnimento di uno stato precedente,
impulso limitato, interruzione durante impulso, errore di conferma dopo
accensione, rifiuto del clock esterno e segnalazione di un arresto fallito.
Eseguire con `python3 -m unittest discover -s tests -v`.

**Prova sul primo motore reale riuscita il 5 novembre 2026:** accensione da
comando software e arresto automatico confermati dall'utente.
Non sono ancora state provate intensita' intermedie, altri motori, piu'
canali simultanei o recupero da guasti hardware sul banco reale.

## Copia del programma sul Mac

Con il Raspberry ancora acceso e collegato tramite USB, aprire una NUOVA
finestra Terminale sul Mac e usare:

```bash
scp lorenzoschillaci@10.55.0.2:hamda_primo_motore.py "$HOME/Downloads/HAMDA_primo_motore_2026-11-05.py"
```

La password richiesta e' quella dell'account Raspberry. Il comando va
eseguito nel Terminale locale del Mac, non nella sessione SSH `@HAMDA`.

## Riprendere la prova e spegnere

Tenere inizialmente scollegato il powerbank del motore. Collegare il
Raspberry al Mac e attendere l'avvio. Aprire una nuova finestra Terminale
sul Mac e accedere con `ssh lorenzoschillaci@10.55.0.2`. Questo evita anche
di riutilizzare una finestra rimasta in una modalita' di incolla errata:
nella sessione erano comparsi prefissi `00~` e suffissi `01~` dopo una
disconnessione SSH; una nuova finestra ha risolto il problema.

Prima di alimentare il motore, nel Raspberry eseguire:

```bash
python3 ~/hamda_primo_motore.py off
```

Controllare il messaggio di uscite impostate spente, poi collegare il
powerbank. Se il motore parte prima del comando, scollegare il powerbank
e controllare il cablaggio. Eseguire una sola prova `pulse`, quindi
scollegare nuovamente il powerbank.

Per terminare, nella sessione SSH del Raspberry (`@HAMDA`) eseguire
`sudo poweroff`, attendere 30 secondi e scollegare il cavo USB dal Raspberry.
La chiusura SSH con `Connection reset` o `Broken pipe` in seguito a questo
spegnimento e' prevista; quegli errori in altri momenti richiedono verifica.
