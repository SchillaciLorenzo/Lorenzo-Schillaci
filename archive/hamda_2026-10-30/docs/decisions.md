# HAMDA — Stato delle decisioni

Questo documento distingue i requisiti ricevuti dalle scelte modificabili del
primo deliverable. La [specifica originale](specification.md) resta il
riferimento per l'intero progetto.

Le informazioni sui componenti realmente posseduti e la valutazione di
un'espansione a 32 motori sono raccolte nell'[inventario hardware](hardware_inventory.md).
L'utente ha confermato quattro schede PCA9685; la compatibilità elettrica resta
da verificare. Il simulatore attuale mantiene la configurazione da 16 motori.

## CONFIRMED — Requisiti confermati

- Il progetto si chiama HAMDA e riguarda Human Factors e assistenza multimodale.
- Il software principale è in Python e deve avere un'architettura modulare.
- La specifica iniziale prevede 16 motori vibranti, 8 per piede, con controllo
  individuale dell'intensità. È stata successivamente discussa un'espansione
  proposta a 32 motori indipendenti.
- Il computer previsto è Raspberry Pi 4 Model B; il PCA9685 genera i segnali PWM
  e i MOSFET gestiscono il pilotaggio dei motori tramite un circuito adeguato.
- Il sistema deve essere trasportabile e prevede alimentazione portatile.
- Il primo deliverable è un'applicazione simulata e testabile, indipendente
  dalle librerie hardware, con intensità individuale, attivazioni temporizzate,
  STOP globale e test di base.
- Il progetto è sperimentale e non costituisce un dispositivo di sicurezza
  certificato per operazioni astronautiche.

## PROPOSED — Scelte attuali modificabili

| Scelta | Motivazione e limiti |
| --- | --- |
| Python 3.10+ per la simulazione | Base software proposta; l'ambiente di sviluppo corrente usa 3.12. La versione sul Raspberry Pi va verificata. |
| Solo libreria standard Python | Permette avvio e test del primo deliverable senza dipendenze hardware o installazioni aggiuntive. |
| CLI e shell interattiva | Consentono prove manuali e controllo dei timer nella stessa sessione. |
| `L1`–`L8`, `R1`–`R8` | ID logici leggibili; non definiscono posizioni anatomiche. |
| Canali 0–7 sinistra, 8–15 destra | Mappatura iniziale configurabile, non cablaggio elettronico definitivo. |
| Posizione anatomica `null` | Registra esplicitamente che la disposizione non è stata definita. |
| Configurazione JSON | Separazione fra mappatura, limiti e codice applicativo. |
| Scala dell'intensità 0–100 | Convenzione software; la conversione numerica non predice la percezione. |
| `max_intensity` 100 e `max_duration_ms` 60000 iniziali | Esempi configurabili per simulazione; nessuna validità elettrica o di sicurezza attribuita. |
| `set` conserva la scadenza | Cambia l'intensità di un'attivazione esistente senza prolungarla implicitamente. |
| Controllo limitato al processo | La shell controlla il proprio controller; altre invocazioni non sono comandi remoti. |
| Tempo monotono per le durate | Le scadenze non dipendono dall'orologio civile; resta assente una garanzia di tempo reale. |

Queste scelte rendono eseguibile il primo prototipo software e possono cambiare
con i risultati delle prove. Non trasformano le proposte della specifica in
risultati scientificamente validati.

## OPEN — Questioni ancora aperte

### Elettronica e dispositivo

- Specifiche nominali dei motori e dei moduli MOSFET, piedinatura, protezioni per
  carichi induttivi e compatibilità con i segnali a 3,3 V.
- Cablaggio, masse, alimentazione e corrente assorbita durante il carico
  simultaneo; verifica della soluzione powerbank proposta.
- Frequenza PWM, limiti d'intensità e durata appropriati per l'hardware reale.
- Disposizione anatomica e corrispondenza definitiva tra ID e attuatori.
- Protezione e interruzione dell'alimentazione indipendenti dal software in
  caso di guasto, blocco o perdita della comunicazione.
- Versioni effettive di Raspberry Pi OS, Python e librerie hardware compatibili.

### Sviluppi successivi

- Backend PCA9685 e prima prova di un singolo canale dopo la verifica elettrica.
- Precisione temporale richiesta e misurazione sul dispositivo.
- Formato dei pattern, ripetizioni e comportamenti di sovrapposizione.
- Priorità e regole di interruzione o sostituzione degli eventi concorrenti.
- Logging sperimentale, sincronizzazione e protocolli degli ingressi esterni.
- Eventuali sensori, computer vision, audio, dashboard o controllo remoto.
- Protocolli di ricerca, distinguibilità dei segnali e metriche di valutazione.

## Limiti della verifica di questa fase

La suite automatica e le prove CLI riguardano il software simulato. Non
dimostrano la vibrazione di un motore reale, la disponibilità del bus I²C,
l'adeguatezza dei parametri elettrici o l'efficacia percettiva dei segnali.

Prima di passare alla fase successiva occorre verificare il funzionamento del
deliverable corrente e risolvere le questioni che sono prerequisiti di quella
fase. Non si attiva automaticamente l'hardware a seguito di un test simulato.
