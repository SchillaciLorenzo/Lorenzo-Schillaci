# Firmware USB TACTUS da banco

Aggiornato al 20 novembre 2026. Il firmware `HAMDA_USB` è stato compilato sul
Raspberry dell'utente, scritto con verifica su **A e B** e riconosciuto su
entrambe le unità tramite `ID` e `STOP`. Usa quattro uscite per modulo, senza
Wi-Fi o MQTT. Il precedente banco PCA9685/DRV resta separato.

Lo [stato canonico del banco](../../docs/STATO_2026-11-20.md) distingue
risultati software, osservazioni fisiche e verifiche aperte. Le prove sul Pi
hanno usato helper inline; il [client host completo](../host/README.md) resta
verificato soltanto offline.

## Risultati acquisiti

- Build reale sul Pi: **Arduino CLI 1.6.0**, **esp32:esp32@3.3.13**,
  ESP32-C3, USB CDC all'avvio, flash **4 MB, DIO/80 MHz**, `--jobs 1`.
  Immagine applicativa: **300192 byte**; il conteggio sketch del compilatore
  è 300038 byte. I numeri descrivono risultati diversi della stessa build.
- Scrittura verificata e risposte ID/OK STOP su A e B. I backup originali
  restano privati sul Raspberry e non sono inclusi nel repository.
- Su B: impulso del motore 1 con arresto autonomo riferito dall'utente;
  gruppo dei quattro funzionante dopo riparazione del cablaggio, con giallo
  su S3 e blu su S4 ripristinati. B2/B3/B4 non sono stati provati singolarmente.
- Su A: gruppo dei quattro e spegnimento autonomo riferiti riusciti. Nessun
  nuovo log ACK incollato per questa prova; nessuna prova individuale A.
- Nella prova combinata tramite helper, l'utente riferisce che vibrano tutti
  e otto. **La conferma dello spegnimento combinato è ancora attesa.** Nessun
  nuovo log ACK, sincronismo o durata fisica misurati vengono dedotti.
- La misura USB-only V/G dei driver di A non è stata eseguita. Le misure
  elettriche di B non vengono attribuite ad A.

## Identità e mappa software

Entrambi i dispositivi sono ESP32-C3 revisione 0.4, flash 4 MB, Secure Boot e
Flash Encryption disabilitati. La whitelist usa la MAC base eFuse senza
avviare Wi-Fi.

| Unità | MAC | Motore 1 | Motore 2 | Motore 3 | Motore 4 |
| --- | --- | --- | --- | --- | --- |
| A | `10:00:3b:cc:97:d8` | GPIO3 | GPIO2 | GPIO1 | GPIO0 |
| B | `10:00:3b:cc:1c:78` | GPIO3 | GPIO2 | GPIO1 | GPIO0 |
| Colore S dichiarato | | Arancio | Verde scuro | Giallo | Blu |

È la mappa del codice, non la prova individuale di tutte le associazioni
fisiche. S3/S4 indicano i collegamenti dei driver, non GPIO3/GPIO4. Una MAC
sconosciuta non configura né scrive GPIO motore e rifiuta PULSE. GPIO18/19,
usati dalla USB nativa, non compaiono nei profili. ON usa HIGH a 3,3 V, OFF
usa LOW; le prove riferite su B non validano elettricamente ogni canale o A.

Entrambe le unità hanno il puntalino rosso ESP 5V rimosso e isolato secondo
la dichiarazione dell'utente. Solo su **B** sono riferiti 2,871 MΩ fra ESP 5V
e V driver, zero ohm fra le masse e 0 V sui driver con sola USB e batteria
scollegata. L'equivalente controllo USB-only di **A resta non eseguito**.

**GPIO2 è un pin di strapping.** Il latch LOW viene preparato prima di OUTPUT
e Serial.begin, ma il programma non controlla i livelli durante ROM,
bootloader o reset. Tenere la batteria motori spenta durante avvio/reset.
STOP e timeout sono comandi software, senza interruzione fisica dell'energia.

## Protocollo ASCII versione 1

Una riga per comando, terminata da LF o CRLF, mai solo CR. Maiuscole esatte,
un solo spazio fra campi, nessuno spazio iniziale/finale. Massimo **31
caratteri**, esclusi CR/LF; interi decimali senza segno. La riga completa deve
arrivare entro **250 ms dal primo byte**: inviarla con una sola write host.

| Comando | Effetto | Risposta normale |
| --- | --- | --- |
| `ID` | Identità, senza attivazione | `ID HAMDA_USB 1 A 10:00:3b:cc:97:d8` oppure B/UNKNOWN e MAC reale |
| `PING` | Verifica comunicazione | `OK PING` |
| `STOP` | Richiede OFF alle quattro uscite conosciute | `OK STOP` |
| `PULSE <mask> <ms>` | Un episodio ON/OFF temporizzato | `OK PULSE <mask> <ms>` |

Maschera **1–15**: bit 0=motore 1, bit 1=motore 2, bit 2=motore 3,
bit 3=motore 4. Le maschere 1/2/4/8 selezionano i singoli motori; 15 li
seleziona tutti. Durata **1–250 ms**. Questi numeri descrivono il protocollo,
non durate fisicamente validate o posizioni anatomiche.

Ogni PULSE è un episodio globale: durante ON nessun nuovo PULSE è accettato,
nemmeno su un altro motore. Maschera e scadenza originali restano invariate.
Una pausa OFF di almeno **250 ms** segue scadenza, STOP o errore di input;
vale anche all'avvio. Il timer locale non richiede altri messaggi host e usa
differenze unsigned resistenti al wrap di millis().

Errori: `ERR ACTIVE`, `ERR COOLDOWN`, `ERR UNKNOWN_DEVICE`, `ERR GPIO`,
`ERR INPUT`. GPIO blocca ulteriori PULSE fino al riavvio; STOP tenta comunque
OFF. Input malformato, byte non ASCII, CR non seguito da LF, overflow o
scadenza della riga richiedono OFF. Dopo overflow/byte invalido/timeout si
scarta fino al successivo LF. Una riga incompleta non sospende il timer.

STOP è elaborato anche durante ON, pausa, guasto o identità sconosciuta.
Il parser ha un budget di **64 byte per loop**, con controllo delle scadenze
attorno a ogni byte. Non scavalca dati ancora nel trasporto USB e non offre
una garanzia di latenza o esecuzione real time.

Le risposte hanno LF e una FIFO di quattro righe; se piena possono essere
scartate, anche gli ACK, senza impedire STOP o timeout. Il loop non chiama
Serial.write durante ON: **l'ACK PULSE può arrivare dopo OFF**. Non c'è un evento OFF
separato. Un ACK descrive il comando software, non una misura di moto,
tensione o spegnimento fisico. Un timeout non autorizza a ripetere PULSE.

L'adattatore usa `HWCDC::setTxTimeoutMs(0)`, availableForWrite e scritture
parziali, con API presenti nel core 3.3.13 usato per la build. Dopo reset la
USB può ri-enumerarsi: riaprire la porta by-id dopo la sua ricomparsa; un
vecchio handle può restituire EIO. Sul banco ID/STOP sono riusciti con una
nuova apertura, senza ulteriore reset.

## Test nativi

Dalla cartella `usb/firmware`, con un compilatore C++11 già disponibile:

```bash
bash tests/run_native.sh
```

Lo script compila in una directory temporanea e la rimuove alla fine.
La verifica iniziale ha superato **20 test** con g++ 14.2.0 e warning come
errori, anche con AddressSanitizer e UndefinedBehaviorSanitizer. LeakSanitizer
non era utilizzabile sotto ptrace ed è stato escluso da quel secondo run.

La suite copre whitelist, startup OFF, maschere, timer, mancata proroga,
pausa, wrap, STOP, parser, frame incompleti, flood RX, errori GPIO e TX solo
OFF con FIFO piena/scritture parziali. I test nativi non compilano l'SDK e non
sostituiscono le prove Arduino e fisiche registrate separatamente.

## Riprodurre la compilazione senza dispositivo collegato

I tre sorgenti in `hamda_usb_bench/hamda_usb_bench.ino` e
`hamda_usb_bench/src/bench_core.{h,cpp}` sono conservati **byte per byte nella
versione compilata sul Pi**. I commenti preparatori restano quelli della fase
di scrittura; per i risultati successivi fa fede lo stato canonico.

Il Pi usa il file dedicato `$HOME/hamda_usb_build/arduino-cli.yaml`.
Dalla cartella `usb/firmware` del repository:

```bash
TACTUS_BUILD="$HOME/hamda_usb_build"
"$TACTUS_BUILD/tools/arduino-cli" --config-file "$TACTUS_BUILD/arduino-cli.yaml" version
"$TACTUS_BUILD/tools/arduino-cli" --config-file "$TACTUS_BUILD/arduino-cli.yaml" core list
"$TACTUS_BUILD/tools/arduino-cli" --config-file "$TACTUS_BUILD/arduino-cli.yaml" board details \
  --fqbn 'esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M,FlashMode=dio,FlashFreq=80'
"$TACTUS_BUILD/tools/arduino-cli" --config-file "$TACTUS_BUILD/arduino-cli.yaml" compile \
  --fqbn 'esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M,FlashMode=dio,FlashFreq=80' \
  --jobs 1 --output-dir "$TACTUS_BUILD/build-riproduzione" hamda_usb_bench
```

Verificare che core list riporti 3.3.13. Il FQBN esplicita **DIO/80 MHz**;
il default QIO del menu generico non è quello usato sul banco. Non servono
librerie esterne al core Espressif. Compilare non esegue upload.

La directory originale del Pi era
`~/hamda_usb_build/progetti/hamda_usb_manuale_20261119`, con output in `build`,
sorella di `hamda_usb_bench`. Il comando sopra usa un output diverso per
registrare una nuova esecuzione senza sostituire gli artefatti già programmati.
Conservare log, versioni, FQBN e hash della nuova build.

Gli helper di flash A/B e i blocchi inline sono una **fotografia del banco del
novembre 2026**: verificano percorsi specifici del Pi, backup privati,
dimensione dell'applicazione e hash ELF/immagine di quella build. Non sono
uploader generici per una compilazione futura. Una nuova build richiede una
nuova registrazione degli artefatti e una procedura di scrittura adatta;
modificare un hash atteso solo per superare una guardia ne annulla il controllo
di provenienza.
