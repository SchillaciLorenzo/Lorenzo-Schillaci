# Client host USB da banco A/B

Aggiornato al 20 novembre 2026. `hamda_usb_bench.py` è verificato con seriali e
orologio finti; **questo entrypoint completo non è stato eseguito sul Pi**.
Le prove reali hanno usato helper Python inline separati, con prompt manuali
per la batteria e conferme diverse secondo il blocco usato. Il protocollo
HAMDA_USB è stato riconosciuto su
A e B; questo risultato non equivale al collaudo di ogni comando di questa CLI.

Lo [stato canonico del banco](../../docs/STATO_2026-11-20.md) registra i risultati
fisici e le verifiche aperte. Il [README firmware](../firmware/README.md)
descrive la build Arduino realmente compilata e programmata.

## Stato delle unità

Entrambe le unità A e B hanno il nuovo firmware scritto con verifica e
risposte ID/OK STOP coerenti. Entrambe hanno il rosso ESP 5V rimosso e isolato
secondo la dichiarazione dell'utente.

Solo su **B** sono riferiti 2,871 MΩ fra le linee positive, zero ohm fra le
masse e 0 V sui driver con sola USB. B ha superato la prima prova del motore 1
e la prova del gruppo dei quattro dopo riparazione di un cavo. Giallo su S3 e
blu su S4 sono stati ripristinati; B2/B3/B4 non sono stati provati singolarmente.

Su **A** sono riferiti funzionamento dei quattro in gruppo e spegnimento
autonomo. Nella successiva prova combinata l'utente ha riferito vibrazione di
**tutti e otto**, ma la conferma esplicita dello spegnimento combinato è ancora
attesa. Non sono stati incollati nuovi log ACK di queste prove. Le prove
individuali A e B2/B3/B4 restano da eseguire.

Il primo tentativo dell'helper combinato è stato annullato prima di aprire
porte o inviare PULSE: era stato scritto `PROVA` al prompt che richiedeva
soltanto Invio. La prova riferita riuscita per la vibrazione degli otto è
quella successiva, con l'helper a conferme solo Invio. Il client completo
documentato qui non è stato eseguito sul Pi.

La misura USB-only V/G dei driver di A non è stata eseguita. Le prove hardware
sono riprese; queste osservazioni non certificano isolamento o sincronismo.

GPIO2 è un pin di strapping: lo stato del firmware non controlla i livelli
prima dell'applicazione. Le batterie motori restano spente durante
avvio/reset. Il banco PCA9685 precedente rimane separato da questo client.

## Eseguire soltanto i test offline

Serve Python 3.10 o successivo. I test usano soltanto la libreria standard,
seriali e orologio finti, lock in directory temporanee; non cambiano `HOME`.

```bash
cd /percorso/usb/host
python3 -m unittest discover -s . -p 'test_*.py' -v
python3 hamda_usb_bench.py --help
```

L'importazione e `--help` non importano pyserial e non aprono porte o lock.
L'avvio senza selezione/azione termina con errore d'uso senza I/O. Il client
non installa dipendenze. Sul Pi pyserial 3.5 nel venv `~/hamda_esp32_tools` è
stato usato dagli helper inline; lo stesso Python serve a esptool 5.6.0.

## Interfaccia del client completo, non ancora collaudata sul Pi

I seguenti comandi descrivono l'interfaccia, **non le esecuzioni già svolte
sui dispositivi**. I prompt batteria/PROVA degli helper inline non sono
inclusi in questo client: questi esempi non sostituiscono quella procedura
fisica e non eseguono flash.

```bash
"$HOME/hamda_esp32_tools/bin/python" hamda_usb_bench.py --unit B off
"$HOME/hamda_esp32_tools/bin/python" hamda_usb_bench.py --unit B primo --ms 250
```

Le scelte obbligatorie sono `--unit A`, `--unit B` o `--unit entrambe` e
`off`, `primo`, `secondo`, `terzo`, `quarto`, `tutti`. Non c'è un'azione
automatica. Durata predefinita e massima: 250 ms, minimo 1 ms. I quattro
motori locali corrispondono alle maschere 1/2/4/8; `tutti` invia maschera 15 alla
singola unità. Non sono numeri GPIO né posizioni anatomiche.

Con `entrambe`, prima vengono verificati ID e STOP di **tutte e due** le
unità e atteso il cooldown. Poi viene inviato un comando PULSE completo ad A
e uno a B **prima di attendere gli ACK**. Con `tutti`, questo richiede tutti
gli otto motori senza attendere la conclusione della prima unità. I due invii USB restano
distinti: non si promette sincronismo fisico o una differenza temporale
misurata. Un errore sul primo invio impedisce il secondo; un errore sul
secondo invio o su qualunque ACK avvia lo STOP best effort di entrambe.
Questa modalità del **client completo** è verificata soltanto con seriali
finte. La vibrazione degli otto riferita sul banco ha usato un helper inline
separato e non dimostra il collaudo di questo entrypoint. L'osservazione non
misura sincronismo, indipendenza individuale o durata; lo spegnimento del
gruppo combinato attende ancora conferma.

## Identità e protocollo

| Unità | MAC attesa | Suffisso della porta by-id |
| --- | --- | --- |
| A | `10:00:3b:cc:97:d8` | `10:00:3B:CC:97:D8-if00` |
| B | `10:00:3b:cc:1c:78` | `10:00:3B:CC:1C:78-if00` |

Le porte complete sono fissate nel sorgente, con prefisso
`/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_`.
Non ci sono scansioni, fallback a `ttyACMx` o associazioni basate sull'ordine
USB. La porta scelta non basta: la risposta deve confermare versione,
lettera e MAC in minuscolo. `UNKNOWN`, MAC diversa e protocollo originale
fanno interrompere il banco prima di qualunque impulso.

```text
ID                 -> ID HAMDA_USB 1 B 10:00:3b:cc:1c:78
STOP               -> OK STOP
PING               -> OK PING
PULSE 1 250        -> OK PULSE 1 250
```

Ogni comando è ASCII terminato da LF e viene inviato con una sola `write`.
Una scrittura parziale è un errore. L'ACK PULSE può arrivare dopo l'impulso;
ogni risposta ha scadenza 1.5 s e limite di 128 byte. `ERR`, risposta
inattesa, overflow, timeout o disconnessione interrompono l'operazione.
Non ci sono richieste da OSC, MQTT, Wi-Fi o altri ingressi esterni.

Il firmware deve spegnere autonomamente entro il limite di banco, anche se
l'host scompare. Il suo cooldown OFF è almeno 250 ms; l'host attende 250 ms
dopo l'ultimo ACK STOP iniziale. L'ACK non è una misura di tensione o moto.
Questo limite software non certifica durata fisicamente ammessa o real time.

## Arresto, concorrenza e limiti

Ogni sessione consente un solo episodio: per riprovare si deve ripetere la
verifica e lo STOP iniziale, senza rinnovare automaticamente impulsi. Prima
di ogni episodio il banco deve essere preparato; alla chiusura tenta
STOP su tutte e sole le unità con identità verificata, anche se il primo
tentativo fallisce. Invia tutti gli STOP prima di attendere gli ACK, quindi
chiude seriali e lock. Se lo STOP finale non è
confermato il programma restituisce errore; non dichiara uscite fisiche OFF.
Se un errore lascia ancora in coda l'ACK PULSE già atteso, la chiusura può
leggere quell'unica risposta prima dell'ACK STOP, senza estendere la deadline.
Errori e altre risposte inattese non vengono ignorati.
Ctrl-C e SIGTERM passano per questa chiusura. Spegnimento del Pi, kill forzato
e guasti richiedono il timer indipendente dell'ESP e un arresto fisico.

Su Linux si usano lock cooperativi per utente sotto
`~/.cache/hamda_usb_bench/locks`, oltre a `exclusive=True` di pyserial. I lock
cooperativi non impediscono l'accesso da programmi che li ignorano o da altri
utenti. Chiudere monitor seriali e altri client prima delle prove.
DTR e RTS vengono impostati False prima di aprire la porta: questo limita
richieste software di reset, ma non garantisce assenza di glitch del driver
USB, del sistema operativo o del circuito di auto-reset.

Dopo un reset la USB può ri-enumerarsi e invalidare il vecchio handle.
Sul banco gli helper inline hanno riaperto la porta, atteso un secondo e
svuotato RX prima di ID. Il client completo non replica questa attesa e
pulizia iniziale: un log ROM pendente può essere rifiutato come risposta
inattesa. Questo comportamento dell'entrypoint resta da verificare sul Pi.

Un ID assente non viene risolto con reset automatici, caricamenti o flash.
Un problema di identità richiede verificare il dispositivo, senza cambiare
MAC o porta attesa per superare il controllo.
