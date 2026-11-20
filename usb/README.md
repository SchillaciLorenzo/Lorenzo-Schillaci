# Banco USB HAMDA

Il codice corrente è in [firmware](firmware/README.md) e
[host](host/README.md). Lo [stato del 20 novembre](../docs/STATO_2026-11-20.md)
distingue prove fisiche, comandi confermati e verifiche ancora da eseguire.
Il lavoro sull'hardware è in pausa per questa pubblicazione.

## File del banco

| Percorso | Contenuto |
| --- | --- |
| `firmware/` | Sorgente Arduino ESP32-C3 comune ad A/B, core portabile e test C++. |
| `host/` | Client riutilizzabile con selezione A/B/entrambe e test seriali simulati. |
| `setup/` | Preparazione separata di Arduino CLI 1.6.0 e core ESP32 3.3.13. |
| `check_a_usb_inline.txt`, `check_b_usb_inline.txt` | Comandi usati per ID e STOP, senza impulsi. |
| `test_first_b_inline.txt`, `test_all_b_inline.txt` | Helper delle prove fisiche B descritte nello stato. |
| `test_remaining_b_inline.txt` | Prova separata B2–B4 preparata ma non eseguita. |
| `test_all_a_inline.txt` | Prova dei quattro A preparata ma non eseguita. |
| `read_b_boot_inline.txt`, `reset_then_check_b_inline.txt` | Diagnostica storica USB. RST può invalidare la porta aperta; riaprirla dopo la ricomparsa del dispositivo. |
| `backup_esp32.sh`, `backup_modulo_B.sh`, `verifica_backup_B.py` | Strumenti locali per conservare e verificare copie della flash; [istruzioni](BACKUP.md). |
| `flash_a.py`, `flash_b.py`, `flash_*_inline.txt` | Scrittura controllata dello specifico snapshot già usato sul Pi. |

Gli helper flash sono vincolati alle identità A/B, ai due backup privati
di ciascuna unità, alla cartella di build originale e agli hash registrati.
Non sono uploader generici per una nuova compilazione: un'immagine o un ELF
diverso deve farli interrompere. Il loro import non scrive dispositivi;
la chiamata esplicita `main(write=True)` dei blocchi inline esegue la procedura.
La build documentata è in [BUILD_SNAPSHOT.json](firmware/BUILD_SNAPSHOT.json).

I file `*_inline.txt` contengono comandi eseguibili da terminale. Le prove
motore includono una pausa per collegare la sola batteria dell'unità scelta,
conferma `PROVA`, un impulso massimo di 250 ms, STOP e disconnessione della
batteria prima della chiusura USB. Non eseguirli durante la pausa hardware.
Gli ACK sono conferme del protocollo, non misure del movimento.

## Test offline

Dalla cartella principale del repository:

```bash
python3 -m unittest discover -s tests -p 'test*.py' -v
python3 -m unittest discover -s usb -p 'test*.py' -v
python3 -m unittest discover -s usb/host -p 'test*.py' -v
python3 -m unittest discover -s usb/setup -p 'test*.py' -v
bash usb/firmware/tests/run_native.sh
```

Questi test usano seriali, file, clock o strumenti simulati e non aprono
i dispositivi dell'utente. I backup binari, i risultati di compilazione,
le configurazioni Wi-Fi e i sorgenti esterni ricevuti non sono inclusi.
