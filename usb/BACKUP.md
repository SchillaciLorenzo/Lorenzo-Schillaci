# Backup locale dell'ESP32-C3 prima della migrazione USB

`backup_esp32.sh` legge la flash del dispositivo già identificato. Non modifica
il firmware, non cancella la flash, non programma eFuse e non riavvia
l'applicazione. Il progetto HAMDA e il protocollo offline rimangono separati.

Il dispositivo osservato è ESP32-C3 QFN32 revisione 0.4, con flash integrata
XMC da 4 MB. L'interfaccia USB stabile attuale è:

```text
/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_10:00:3B:CC:97:D8-if00
```

Prima dell'esecuzione il chip deve essere già nel bootloader, come lasciato
dall'ispezione esptool. Mantieni la batteria spenta e le schede driver GVS
scollegate; l'ESP rimane alimentato soltanto da USB. Chiudi eventuali monitor
seriali che occupano la stessa porta.

Il comando utilizza il venv esptool già installato sul Raspberry Pi
(`~/hamda_esp32_tools`, esptool 5.6.0, Python 3.13):

```bash
bash backup_esp32.sh
```

La cartella nuova `~/HAMDA_backup_ESP32_XXXXXXXX` è privata. Lo script:

1. Rilegge le informazioni di sicurezza e procede soltanto con Flags zero,
   Secure Boot `Disabled` e Flash Encryption `Disabled`, in formato riconosciuto.
2. Registra l'identificazione della flash e legge due volte l'intera flash,
   usando soltanto il bootloader ROM, senza stub e senza reset tra le letture.
3. Verifica che entrambe le copie siano di 4194304 byte, identiche byte per
   byte e con lo stesso SHA-256.
4. Crea `SHA256SUMS` con nomi relativi e `VERIFIED.txt` soltanto dopo i controlli.

La lettura ROM può essere lenta. Non scollegare o riavviare l'ESP tra le
letture: eseguire il vecchio firmware potrebbe cambiare dati NVS.

In caso di errore lo script si ferma, conserva log e copie parziali nella
cartella appena creata e non lascia `VERIFIED.txt`. Non trattare quelle copie
come backup verificati. Nessun errore viene risolto cancellando o forzando
protezioni.

Per ricontrollare in seguito i file, entra nella cartella del backup ed esegui:

```bash
sha256sum -c SHA256SUMS
```

Le due letture identiche dimostrano una copia stabile, non un ripristino
collaudato. I binari possono contenere credenziali: conservali privatamente
sul Pi e non caricarli in chat o repository.

Per scegliere percorsi diversi esistono solo questi override:

- `HAMDA_ESP32_PYTHON`: percorso di un interprete eseguibile con esptool.
- `HAMDA_ESP32_PORT`: dispositivo seriale a caratteri identificato esplicitamente.
- `HAMDA_ESP32_BACKUP_PARENT`: cartella esistente e scrivibile per il backup.

Gli override non cambiano il modello atteso o la dimensione verificata di
4 MB. Non usare lo script su un dispositivo diverso senza riesaminare quei
requisiti.
