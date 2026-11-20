# HAMDA — Banco USB sperimentale a due moduli

Questo repository raccoglie il lavoro sul banco USB di HAMDA: un firmware
ESP32-C3 comune alle unità A e B e un programma Python che le comanda dal
Raspberry. Ogni modulo ha quattro uscite; otto motori sono l'obiettivo del
banco a due moduli. Il progetto HAMDA completo comprende sviluppi ulteriori.

**Stato al 20 novembre 2026:** nuovo firmware scritto e identificato su A e B.
Su B sono riferite prove fisiche riuscite del primo motore e dei quattro in
gruppo. Su A sono riferiti funzionamento dei quattro e spegnimento autonomo.
Nella successiva prova combinata l'utente ha confermato che **tutti e otto
vibrano e si fermano da soli prima di spegnere le batterie**. Il primo test
di gruppo A+B è riuscito. I dettagli sono in
[Stato del banco](docs/STATO_2026-11-20.md).

Il [resoconto delle verifiche offline](docs/VERIFICA_2026-11-20.md) registra
282 test Python e 20 test C++ superati per gli aggiornamenti pubblicati.

## Materiale precedente e inventario

- [Progetto originale, specifica e inventario del 30 ottobre](archive/README.md).
- [Componenti acquistati](docs/purchased_components.md).
- Banco PCA9685/DRV precedente: sorgenti in `tools/`, test in `tests/` e guide
  storiche in `docs/`.
- [Preview offline dei messaggi TACTUS](integration/tactus_preview/README.md).

## Organizzazione

```text
usb/
├── firmware/
│   ├── hamda_usb_bench/
│   │   ├── hamda_usb_bench.ino
│   │   └── src/bench_core.h, bench_core.cpp
│   └── tests/
├── host/
│   ├── hamda_usb_bench.py
│   └── test_hamda_usb_bench.py
└── setup/
    └── install_arduino.sh
```

I comandi seguenti partono dalla cartella principale del repository. Nessun
comando di test o compilazione qui sotto carica firmware sui dispositivi.

## Verifiche offline

Per i test host serve Python 3.10 o successivo. Si usano seriali finte e la
libreria standard; pyserial non è necessario per questi test.

```bash
python3 -m unittest discover -s usb/host -p 'test_*.py' -v
bash usb/firmware/tests/run_native.sh
python3 usb/host/hamda_usb_bench.py --help
```

Il secondo comando richiede un compilatore C++11, ad esempio g++. Queste
verifiche riguardano logica, protocollo e comportamento simulato. Non misurano
le tensioni, il movimento dei motori o il comportamento USB reale.

## Strumenti e compilazione del firmware

La configurazione riprodotta sul Raspberry usa:

- Arduino CLI **1.6.0** e Arduino-ESP32 **3.3.13**;
- target ESP32-C3, USB CDC all'avvio, flash **4 MB**, modalità **DIO**, **80 MHz**;
- configurazione dedicata `~/hamda_usb_build/arduino-cli.yaml`.

Su una nuova macchina Linux ARM64, lo script prepara gli strumenti in due fasi
con verifica dei download. Sul Raspberry già preparato non serve reinstallare
automaticamente ciò che è presente:

```bash
bash usb/setup/install_arduino.sh --cli-only
bash usb/setup/install_arduino.sh --core
```

Per compilare soltanto, conservando separati sorgenti e nuovi artefatti:

```bash
hamda_build_root="$HOME/hamda_usb_build"
hamda_compile_dir="$(mktemp -d "$hamda_build_root/build_repo_XXXXXXXX")"
"$hamda_build_root/tools/arduino-cli" \
  --config-file "$hamda_build_root/arduino-cli.yaml" compile \
  --fqbn 'esp32:esp32:esp32c3:CDCOnBoot=cdc,FlashSize=4M,FlashMode=dio,FlashFreq=80' \
  --jobs 1 --output-dir "$hamda_compile_dir" usb/firmware/hamda_usb_bench
```

Prima di confrontare gli artefatti, registra versione degli strumenti, FQBN,
log, dimensioni e SHA-256. Differenze di percorso o ambiente possono influire
sulla build: non presumere identità binaria senza misurarla. La procedura di
scrittura flash resta separata e legata alla specifica unità e ai suoi backup.

## Programma host

L'accesso reale richiede pyserial **3.5**. Sul Raspberry il venv già usato è
`~/hamda_esp32_tools`; per una nuova macchina si può preparare un ambiente
separato:

```bash
python3 -m venv .venv-host
.venv-host/bin/python -m pip install 'pyserial==3.5'
```

Il programma importa pyserial soltanto quando apre una sessione richiesta.
Verifica unità, versione del protocollo, MAC e porta USB stabile; non ripiega
su un dispositivo trovato casualmente. Le identità in firmware e host sono
quelle del banco attuale: altri dispositivi richiedono un'integrazione esplicita.

Sul banco sono stati eseguiti gli helper inline descritti nello stato. Il
client riutilizzabile qui elencato è verificato offline e non è ancora stato
copiato o eseguito sul Raspberry.

Questa tabella documenta la sintassi e distingue le prove riferite dagli
aspetti ancora da verificare; non è una sequenza automatica di test.
Nel venv nuovo sostituisci l'interprete del Pi con `.venv-host/bin/python`.

| Operazione | Comando sul Pi | Evidenza fisica attuale |
| --- | --- | --- |
| Identità e STOP B | `"$HOME/hamda_esp32_tools/bin/python" usb/host/hamda_usb_bench.py --unit B off` | Confermati sul banco. |
| Primo motore B | `"$HOME/hamda_esp32_tools/bin/python" usb/host/hamda_usb_bench.py --unit B primo --ms 250` | Vibrazione e spegnimento riferiti. |
| Motore B separato | Stessa sintassi con `secondo`, `terzo` o `quarto`. | Prove individuali B2–B4 da eseguire. |
| Quattro motori B | Stessa sintassi con `--unit B tutti --ms 250`. | Prova di gruppo riferita riuscita. |
| Identità e STOP A | Stessa sintassi con `--unit A off`. | Confermati sul banco. |
| Motore A separato | Stessa sintassi con `--unit A primo --ms 250`. | Prova individuale non eseguita. |
| Quattro motori A | Stessa sintassi con `--unit A tutti --ms 250`. | Gruppo e spegnimento autonomo riferiti riusciti. |
| Otto motori richiesti | Stessa sintassi con `--unit entrambe tutti --ms 250`. | Vibrazione degli otto e arresto autonomo riferiti riusciti tramite helper. |

Per le nuove prove di gruppo non sono stati incollati ulteriori log ACK.
L'osservazione degli otto non dimostra sincronismo temporale o indipendenza
individuale di tutti i canali. Il client completo resta distinto dagli helper
effettivamente usati sul Pi.

Ogni sessione verifica prima ID e STOP, invia al massimo un episodio e tenta
STOP alla chiusura. Il firmware limita l'episodio a 250 ms e impone una pausa
OFF di almeno 250 ms. Sono limiti software del banco, non parametri certificati
di esposizione. Gli ACK confermano comandi logici, non sensori del movimento.

Il firmware usa GPIO3, GPIO2, GPIO1 e GPIO0 per i quattro canali. GPIO2 è un pin
di strapping: il controllo dell'applicazione non copre reset e bootloader.
Durante collegamento, reset e programmazione si mantiene spenta/scollegata
l'alimentazione dei motori. STOP non interrompe fisicamente quella sorgente.

## Tracciare il progetto senza esporre i backup

Git conserva sorgenti, test, istruzioni e risultati sintetici. I backup completi
delle flash restano privati sul Raspberry: per ciascuna unità esistono due
letture identiche da 4 MiB. Non includere i loro file binari nei commit.

Questa pubblicazione non richiede sorgenti grezzi esterni o ESA, credenziali,
configurazioni Wi-Fi, password, contatti personali o dump della memoria.
Il precedente banco PCA9685 in `tools/`, `tests/` e nelle guide storiche
resta distinto da questo banco USB. La [preview dei messaggi TACTUS](integration/tactus_preview/README.md) è una simulazione offline archiviata. Il firmware sperimentale non costituisce il
progetto HAMDA definitivo né un dispositivo certificato.

Gli archivi ZIP delle consegne precedenti restano conservati nella cronologia
e nei branch di download. Il codice corrente è consultabile direttamente in Git.
