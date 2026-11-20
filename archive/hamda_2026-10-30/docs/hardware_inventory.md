# HAMDA — Componenti disponibili ed espansione proposta

Questo inventario raccoglie le informazioni fornite dall'utente nella chat.
La disponibilità di componenti e canali di comando non dimostra la compatibilità
elettrica del circuito. La specifica originale resta in [specification.md](specification.md).

Il successivo [elenco dei 21 acquisti](purchased_components.md), ricevuto il
27 ottobre 2026, conserva l'ordine dei link e dispone di una
[tabella CSV per le quantità](purchased_components.csv). L'utente sta fornendo
il conteggio: non confondere confezioni acquistate e singole schede o motori.

## CONFIRMED — Informazioni ricevute

| Componente | Evidenza | Stato della verifica |
| --- | --- | --- |
| Schede PCA9685 | L'utente dichiara di possederne **4**. | Quantità dichiarata; modello esatto della scheda, cablaggio e indirizzi I²C non verificati. |
| Motori vibranti | L'utente conferma **50 motori singoli** il 28 ottobre 2026; link indicato: `B0C7PFN8H4`. | Quantità dichiarata; tipo di attuatore, tensione e corrente ancora da verificare. |
| Moduli indicati come DM0018x8 | L'ultima precisazione dell'utente, il 28 ottobre 2026, è: **4 PCA9685 e 12 DM0018x8**. | Quantità dichiarata; sigla trascritta dall'utente. Funzione, modello esatto, canali e relazione con la foto precedente da verificare. Non dedurre otto canali dal suffisso. |
| Schede della foto precedente | La confezione nella foto `IMG_8943.HEIC` è identificata come **DRV8833**, modello commerciale `DRV8833-6`. | L'associazione del conteggio di 12 schede a questi DRV8833 è ritirata dopo la precisazione DM0018x8. Non è confermato che si tratti delle stesse schede; nessuna quantità attuale assegnata ai DRV8833. |
| Convertitori di alimentazione | L'utente indica moduli **MP1584EN** con un titolo commerciale che li descrive come step-down regolabili. | Sono convertitori di tensione; non sostituiscono i driver dei motori. Specifiche dell'inserzione non verificate. |

Il DRV8833 dispone di due canali di pilotaggio per motori DC. Questa proprietà
non può essere trasferita automaticamente ai moduli chiamati DM0018x8:
occorre prima identificarli dalla foto e dalla documentazione pertinente.
Il precedente conteggio di 50 motori resta una dichiarazione separata; la
precisazione sulle schede non è stata interpretata come un suo annullamento.

## PROPOSED — Espansione a 32 motori indipendenti

L'utente sta valutando il passaggio da 16 a 32 motori. Questa discussione non
cambia automaticamente la configurazione del software esistente.

- Le quattro schede PCA9685 offrono complessivamente **64 canali PWM potenziali**.
- Per 32 motori DC usati in un solo verso, prevedendo un segnale PWM per motore
  e l'altro ingresso del relativo driver mantenuto allo stato appropriato,
  **due PCA9685** forniscono i 32 comandi separati. Le altre due schede possono
  restare disponibili come riserva.
- Il numero di motori pilotabili con i **12 moduli DM0018x8** è **da verificare**.
  Il precedente calcolo di 24 canali, basato sull'associazione a DRV8833, non è
  applicabile al nuovo inventario senza confermare il modello. Analogamente non
  è stato concluso che manchino quattro driver né che ogni DM0018x8 abbia otto
  canali. Se si adottassero DRV8833 a due canali, 32 motori DC richiederebbero
  16 moduli compatibili; questa è un'ipotesi di architettura, non il conteggio
  dell'hardware attualmente identificato.
- Le schede PCA9685 collegate allo stesso bus I²C devono avere indirizzi distinti.
  Gli indirizzi effettivi e la configurazione dei ponticelli non sono ancora
  stati assegnati o verificati.
- Condividere lo stesso segnale PWM fra due motori produrrebbe invece coppie
  con lo stesso comando; non è necessario farlo con due schede PCA9685.

Questa è una valutazione della capacità di comando, non uno schema di
collegamento già verificato. Non sono stati fissati frequenza PWM, tensioni di
alimentazione, piedinatura dei moduli o limiti di corrente.

### Software attuale

Il primo deliverable resta il simulatore da **16 motori**, con 49 test superati
alla sua verifica iniziale. Non è ancora un'applicazione da 32 motori.

L'espansione richiederebbe una mappatura che distingua **scheda e canale**,
l'estensione degli ID logici, del backend simulato, della validazione e del
diagnostico, insieme a test di indipendenza e STOP su tutti i 32 canali.
Un backend fisico PCA9685/DRV8833 non è ancora implementato.

## OPEN — Dati necessari prima del circuito

- Modello, tipo di attuatore, tensione nominale, corrente di funzionamento e
  corrente di avvio o stallo dei motori. La disponibilità dichiarata è di 50
  motori; quanti usarne nel prototipo resta da definire.
- Uscite effettive del powerbank e capacità di alimentare il carico previsto,
  tenendo conto anche del Raspberry Pi e degli avviamenti simultanei.
- Identificazione esatta dei moduli indicati come DM0018x8, loro relazione con
  i DRV8833 fotografati, numero di canali, schema, ingressi, protezioni e limiti
  elettrici e termici del modello effettivo.
- Regolazione e capacità dei convertitori, masse, cablaggio e interruzione
  fisica dell'alimentazione.
- Scelta del numero di motori del prototipo e disposizione sui piedi.

La prima prova fisica resta su un solo motore, dopo la verifica dei componenti
e del circuito. Il controllo di 32 motori non implica che l'alimentazione possa
sostenerli o che i parametri siano appropriati per prove indossabili.

## Riferimenti forniti dall'utente

Le pagine Amazon non sono risultate accessibili dall'ambiente cloud; dai soli
link non sono state ricavate specifiche elettriche.

- PCA9685: <https://amzn.eu/d/07x1NT6M>
- Motori: <https://www.amazon.de/dp/B0C7PFN8H4>
- Powerbank: <https://www.amazon.de/dp/B0GSY5CXFF>
- Convertitori MP1584EN: <https://www.amazon.de/dp/B0B92WYRR4>
- Driver DRV8833: <https://www.amazon.de/dp/B0DHRFRG6X>, associato alla foto
  dall'ASIN leggibile sull'etichetta; confezione nominale da 6 schede,
  quantità attuale non confermata dopo la precisazione sui 12 DM0018x8.
- Ulteriore inserzione, prodotto non identificato dal link:
  <https://www.amazon.de/dp/B07Y9PTY12>
- Foto dei driver allegata dall'utente: `IMG_8943.HEIC`.
