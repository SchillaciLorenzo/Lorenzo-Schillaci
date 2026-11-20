# HAMDA — Elenco degli acquisti fornito dall’utente

Elenco ricevuto il 27 ottobre 2026: **21 link distinti**, nello stesso ordine
del messaggio dell’utente. L’utente dichiara che questi sono i prodotti presenti
sul tavolo e che comunicherà le quantità. Le quantità non ancora fornite
restano vuote; una confezione non equivale necessariamente a un singolo pezzo.

La tabella [CSV modificabile](purchased_components.csv) contiene campi separati
per confezioni acquistate, pezzi nominali per confezione e pezzi totali.
Le indicazioni di confezione non sono ancora il conteggio fisico dei pezzi.

Quantità confermata dall'utente il 28 ottobre 2026: **50 motori singoli**,
corrispondenti al prodotto **n. 21**. Il numero di confezioni acquistate e il
contenuto nominale della confezione restano non specificati.

L'ultima precisazione dell'utente, il 28 ottobre 2026, indica **12 moduli
chiamati DM0018x8**, oltre alle quattro schede PCA9685. L'associazione automatica
delle 12 schede ai DRV8833 del prodotto n. 7 è ritirata: serve identificare il
modulo e collegarlo al corretto prodotto. La quantità del n. 7 resta quindi
non assegnata; la quantità 12 è conservata nell'inventario sotto DM0018x8.

| N. | Codice e link | Identificazione attuale | Pezzi nominali per confezione |
| --- | --- | --- | --- |
| 1 | [B0GSY5CXFF](https://www.amazon.de/dp/B0GSY5CXFF) | Powerbank; modello e uscite da verificare | Da verificare |
| 2 | [B0GY3CM4KY](https://www.amazon.de/dp/B0GY3CM4KY) | Da identificare | Da verificare |
| 3 | [B0CMQBD1C3](https://www.amazon.de/dp/B0CMQBD1C3) | Da identificare | Da verificare |
| 4 | [B0DH2H1SKL](https://www.amazon.de/dp/B0DH2H1SKL) | Da identificare | Da verificare |
| 5 | [B0F327WFRC](https://www.amazon.de/dp/B0F327WFRC) | Da identificare | Da verificare |
| 6 | [B0B92WYRR4](https://www.amazon.de/dp/B0B92WYRR4) | Convertitori MP1584EN step-down | 6 |
| 7 | [B0DHRFRG6X](https://www.amazon.de/dp/B0DHRFRG6X) | Driver per motori DRV8833, modello commerciale DRV8833-6 | 6 |
| 8 | [B07Y9PTY12](https://www.amazon.de/dp/B07Y9PTY12) | Da identificare | Da verificare |
| 9 | [B09F9J7ZXV](https://www.amazon.de/dp/B09F9J7ZXV) | Da identificare | Da verificare |
| 10 | [B0G8LX3JFM](https://www.amazon.de/dp/B0G8LX3JFM) | Da identificare | Da verificare |
| 11 | [B0DH2B36G5](https://www.amazon.de/dp/B0DH2B36G5) | Da identificare | Da verificare |
| 12 | [B0FP4J6NH1](https://www.amazon.de/dp/B0FP4J6NH1) | Da identificare | Da verificare |
| 13 | [B0D8TG5X2B](https://www.amazon.de/dp/B0D8TG5X2B) | Da identificare | Da verificare |
| 14 | [B0BPPBLZ34](https://www.amazon.de/dp/B0BPPBLZ34) | Da identificare | Da verificare |
| 15 | [B0F7HFQ4YJ](https://www.amazon.de/dp/B0F7HFQ4YJ) | Da identificare | Da verificare |
| 16 | [B0FKXZZHPW](https://www.amazon.de/dp/B0FKXZZHPW) | Da identificare | Da verificare |
| 17 | [B087785H1J](https://www.amazon.de/dp/B087785H1J) | Da identificare | Da verificare |
| 18 | [B0DJ5CHQ33](https://www.amazon.de/dp/B0DJ5CHQ33) | Da identificare | Da verificare |
| 19 | [B0FS772W77](https://www.amazon.de/dp/B0FS772W77) | Da identificare | Da verificare |
| 20 | [B0FB8V2FDY](https://www.amazon.de/dp/B0FB8V2FDY) | Da identificare | Da verificare |
| 21 | [B0C7PFN8H4](https://www.amazon.de/dp/B0C7PFN8H4) | Motori vibranti; modello e caratteristiche da verificare | Da verificare |

## Come leggere i dati

- **N. 1 e 21:** l’associazione a powerbank e motori viene dai precedenti
  messaggi dell’utente, non da una lettura delle pagine Amazon.
- **N. 6:** il titolo incollato dall’utente identifica convertitori MP1584EN
  e riporta una confezione da 6; dato commerciale da confrontare con i pezzi.
- **N. 7:** sulla foto `IMG_8943.HEIC` si leggono ASIN `B0DHRFRG6X`,
  modello `DRV8833-6` e confezione da 6 schede. Questo collega il link alla foto,
  senza stabilire quante confezioni siano state acquistate.
- Gli altri prodotti restano **da identificare**. Il codice ASIN da solo non
  è una specifica elettrica e non è stato usato per indovinare i prodotti.
- L’accesso alle pagine Amazon è risultato bloccato dall’ambiente cloud.
  Titoli copiati, foto o schermate dei soli prodotti permetteranno di completare
  i nomi; non servono documenti di acquisto o dati personali.
- Le **4 schede PCA9685** già dichiarate rimangono registrate nell’inventario:
  non sono ancora associate a uno specifico link di questo elenco.
- Il conteggio più recente è di **12 moduli indicati come DM0018x8**. Non è
  ancora confermato che siano i DRV8833 della foto. Il totale del prodotto n. 7
  rimane vuoto; la precedente stima di almeno 16 driver non è valida.

L’[inventario hardware](hardware_inventory.md) descrive ruoli dei componenti,
ipotesi dell’espansione e verifiche ancora aperte. Nessun nuovo collegamento
o parametro elettrico è stato definito in base a questo elenco.
