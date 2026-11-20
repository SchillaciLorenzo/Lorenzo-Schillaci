# Progetto HAMDA del 30 ottobre 2026

La cartella [hamda_2026-10-30](hamda_2026-10-30/README.md) rende consultabili
in Git i sorgenti, i test, la specifica e l'inventario contenuti nel precedente
archivio `HAMDA_per_Codex_2026-10-30.zip`. I file estratti sono conservati
senza modifiche; gli allegati fotografici non sono stati duplicati.

È una versione storica del simulatore e della configurazione iniziale.
Per il banco attuale con due ESP32-C3 e otto motori previsti, usare il
[README principale](../README.md) e lo [stato del banco](../docs/STATO_2026-11-20.md).
I requisiti o i comandi del progetto storico non sono istruzioni per la
cintura USB attuale.

- [Inventario hardware storico](hamda_2026-10-30/docs/hardware_inventory.md)
- [Componenti acquistati, versione storica](hamda_2026-10-30/docs/purchased_components.md)
- [Specifica iniziale](hamda_2026-10-30/docs/specification.md)

Test del progetto storico, dalla cartella principale del repository:

```bash
cd archive/hamda_2026-10-30
python3 -m unittest discover -s tests -p 'test*.py' -v
```
