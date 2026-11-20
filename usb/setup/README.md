# Preparare Arduino sul Raspberry, senza collegamenti seriali

`install_arduino.sh` prepara soltanto gli strumenti di compilazione.
Versioni fissate: **Arduino CLI 1.6.0 Linux ARM64** e
**core Espressif `esp32:esp32@3.3.13`**. Non compila, non carica firmware,
non legge ESP e non modifica il venv dei backup o il profilo Arduino globale.
Le batterie dei motori restano scollegate durante questa preparazione.

## Esito riferito dal Pi il 19 novembre 2026

La prima fase ha reso disponibile **Arduino CLI 1.6.0**. Il primo tentativo del
core 3.3.13 era **incompleto**: dopo gli indici, i builtin e diversi archivi
Espressif già scaricati, `esp32c6-libs@3.3.13` si è fermato con
`Download failed: context canceled`. Il log non ne stabilisce la causa.

Quel tentativo non aveva raggiunto i controlli finali. Il **retry è ora
completato sul Pi**, secondo l'output dell'utente: dettagli della scheda e
`INSTALLAZIONE ESP32 COMPLETATA.` dallo script con `set -e` e core fissato
3.3.13. L'ultimo allegato contiene il finale di board details, non l'intestazione
di core list. Non si tratta di una verifica hardware autonoma del Cloud.

Nel retry descritto in [`../resume_core_pi.txt`](../resume_core_pi.txt),
`ARDUINO_NETWORK_CONNECTION_TIMEOUT=600s` valeva solo nel sottoprocesso Bash.
Nessuna modifica permanente del file di configurazione, cancellazione della
cache o nuova fase esplicita update-index. La documentazione CLI 1.6.0
definisce questa impostazione come timeout di **inattività** della connessione,
default60s; il successo dopo l'adeguamento non dimostra la causa del precedente
errore. Nessun ESP è stato programmato e la compilazione Arduino resta distinta.

## Due fasi separate

Dalla cartella che contiene lo script, la prima fase è:

```bash
bash install_arduino.sh --cli-only
```

Scarica soltanto il CLI, controlla il SHA-256 ufficiale **prima** di estrarlo
o eseguirlo, crea la configurazione dedicata e richiede versione 1.6.0 in JSON.
Nessun core/SDK viene installato da questa fase. Il blocco equivalente breve
per il Terminale del Pi è mantenuto separatamente in
[`../install_cli_pi.txt`](../install_cli_pi.txt).

La seconda fase, dopo aver verificato il risultato della prima, è:

```bash
bash install_arduino.sh --core
```

Usa il CLI già presente, riconfrontandolo con l'archivio verificato. Aggiorna
gli indici ufficiali, installa esattamente il core 3.3.13, controlla la versione
effettivamente installata in `core list --format json` e richiede i dettagli
del target `esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M`.
Gli script post-installazione sono esclusi; non vengono installati driver
di sistema. La fase non prova che il firmware compili o che i motori funzionino.

## Percorsi e ripetizione

Tutto viene mantenuto sotto **`$HOME/hamda_usb_build`**:

- `tools/arduino-cli`: unico eseguibile CLI installato dalla procedura.
- `arduino-cli.yaml`: configurazione JSON valida anche come YAML.
- `data`, `downloads`, `user`: dati, cache dei pacchetti e spazio utente Arduino.
- `logs`: log distinti delle due fasi.
- `tmp`: directory temporanee rimosse al termine di ogni tentativo.
- `arduino-cli_1.6.0_Linux_ARM64.tar.gz`: archivio verificato conservato.

La posizione dell'archivio e la configurazione coincidono con il blocco
breve della prima fase. Anche `version` viene sempre chiamato con
`--config-file`: invocarlo senza configurazione può inizializzare
`~/.arduino15`, che questa procedura evita.

La configurazione esistente viene conservata se semanticamente uguale,
anche con formattazione diversa; una configurazione diversa non viene
sovrascritta. Variabili Arduino dei processi figli fissano le tre directory
dedicate per evitare che impostazioni ereditate reindirizzino il setup globale.
Non vengono cambiati `PATH`, `HOME` o file del profilo shell.

Download HTTPS con retry3, timeout di connessione20s e limite300s per tentativo.
Il nuovo archivio usa `.tmp` e diventa definitivo soltanto dopo il checksum.
Un archivio valido già presente viene ricontrollato e riutilizzato; una cache
corrotta causa errore anziché disabilitare il controllo. Il core usa le cache
del package manager: dopo un errore risolto si può ripetere la stessa fase.

Servono Linux `aarch64`, almeno **8 GiB liberi** e gli strumenti essenziali
indicati dallo script. Il core richiede circa **1.2 GB compressi**, prima
dell'estrazione e delle cache; il requisito di spazio è un controllo iniziale,
non una garanzia contro future scritture di altri processi sul disco.
Le operazioni sono bloccate se un'altra esecuzione usa la stessa cartella.

Ogni errore interrompe la fase con codice non zero e indica il log disponibile.
Non presentare un errore di installazione come build completata. Non rimuovere
verifiche TLS/hash, non usare sudo e non aggiungere upload per risolvere un errore.

`HAMDA_USB_BUILD_ROOT` permette un'altra cartella dedicata; è usato nei test
offline con directory temporanee senza modificare `HOME`. Percorsi con spazi
sono trattati come dati, non come codice shell.

## Verifica offline dell'installer

```bash
python3 -m unittest discover -s . -p 'test_install_arduino.py' -v
```

I test usano un archivio fixture costruito dal test, un CLI finto e un curl
finto, senza rete, SDK o seriali. Il checksum della fixture è fissato soltanto
in una copia temporanea dello script; il pin SHA-256 ufficiale dello script
di produzione rimane immutato. Non sono prove di un'installazione reale sul Pi.
