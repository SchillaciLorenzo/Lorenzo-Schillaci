> Documentazione storica del banco PCA9685/DRV. Per la cintura con due ESP32-C3 USB leggere lo [stato attuale](STATO_2026-11-20.md).

# HAMDA: banco funzionante a quattro motori, 9 novembre 2026

Il nuovo programma e' installato sul Raspberry. L'utente ha riferito
"PCA: uscite impostate spente." e, dopo aver eseguito la prova tutti,
ha confermato "perfetto funziona tutto" e chiesto di salvare gli
aggiornamenti. La prova simultanea e l'arresto descritti nelle istruzioni
sono quindi confermati dall'utente. L'impulso software e' 0,25 secondi;
la durata meccanica non e' stata misurata.

Il banco a due motori ha funzionato anche dopo il riavvio del 9 novembre.
L'utente ha chiesto di duplicare il circuito, precisando che non intendeva
una copia della microSD. Una risposta tardiva alla precedente domanda
sul backup non ha sostituito questa precisazione.

## Stato del montaggio

L'utente dichiara saldati tutti i pin della seconda DRV8833 e collegati
tutti i cavetti secondo la tabella seguente. Ha spiegato di non poter
fotografare i collegamenti a causa dei numerosi cavi attorcigliati:
proseguire con il controllo a impianto spento seguendo ogni filo e i nomi
stampati. La prova simultanea dei quattro motori e' ora confermata;
le prove separate terzo e quarto non sono state riferite singolarmente.
Tenere scollegato il powerbank prima dei controlli e del trasferimento.

| Seconda DRV8833 | Collegamento previsto |
| --- | --- |
| IN1 | PCA9685 pin giallo, gruppo 2 |
| IN3 | PCA9685 pin giallo, gruppo 3 |
| IN2, IN4, GND | Negativo comune breadboard/regolatore/PCA |
| VCC, SLEEP | Positivo motori circa 3 V del regolatore |
| OUT1, OUT2 | Motore 3 |
| OUT3, OUT4 | Motore 4 |
| FAULT | Libero |

Usare fori liberi degli stessi tratti di alimentazione della breadboard,
considerando eventuali interruzioni delle file. Le uscite rosse V+ della
PCA restano libere. La prima DRV mantiene IN1 al giallo PCA 0 e IN3 al
giallo PCA 1. Logica PCA a 3,3 V dal Raspberry; motori a circa 3 V dal
regolatore, con negativo comune. Non unire i positivi 3,3 V e 3 V.

Prima di toccare i fili, scollegare il powerbank, spegnere il Raspberry
con sudo systemctl poweroff, attendere 30 secondi e scollegare POWER IN.

## Programma installato sul Raspberry

tools/hamda_quattro_motori.py e' autonomo, con sola libreria standard e
lo stesso lock .hamda-pca40.lock delle versioni precedenti. Il programma
collaudato tools/hamda_banco.py conserva il suo contenuto originale.
File corrente sul Raspberry: ~/hamda_quattro_motori.py.
SHA256: 158cb0fed760db8d63f450f5a22d65809d2c3ca06550a8f2368dd85f04e8ffb9.

| Comando del nuovo file | Motori selezionati |
| --- | --- |
| off | Nessuno, tutte le uscite impostate spente |
| primo | 1, PCA 0 |
| secondo | 2, PCA 1 |
| terzo | 3, PCA 2 |
| quarto | 4, PCA 3 |
| insieme | 1 e 2, significato conservato |
| coppia2 | 3 e 4 |
| tutti | 1, 2, 3 e 4; prova simultanea confermata |

Impulso nominale sempre 0,25 s, senza PWM di intensita'. Spegnimento di
tutte le 16 uscite prima della configurazione e alla fine; verifica di
OFF_H su tutte e quattro le uscite usate. I tentativi di spegnimento
proseguono anche dopo un errore su una singola uscita. Le protezioni
software non garantiscono l'arresto durante un blocco del sistema,
SIGKILL o guasto persistente I2C. Disconnessione del powerbank accessibile.

Nove test nel workspace superati: selezione delle sette prove e durata,
spegnimento iniziale di tutte le uscite, interruzione, conferma persa
durante ciascuna delle quattro attivazioni, errore di arresto su ciascuna
uscita senza saltare le altre, rilevamento di arresto ignorato su ognuna
delle quattro uscite, clock esterno, selezioni invalide e lock condiviso.
La prova fisica tutti e' confermata separatamente dall'utente.

## Trasferimento senza rete

Il blocco per il Terminale del Mac e' preparato in
/workspace/exports/copia_quattro_motori_su_sd_mac.txt. Scrive soltanto
hamda_quattro_motori.py nella bootfs, con verifica SHA256 e compilazione
prima della rinomina. Non modifica i file di avvio o hamda_banco.py.
La sintassi Bash e l'identita' del sorgente incorporato sono verificate.
Per trasferire serve il Raspberry spento e senza POWER IN, con la SD nel
lettore del Mac e bootfs montata. Dopo il trasferimento espellere bootfs.

Riportare la SD nel Raspberry. Avviare sul monitor locale con powerbank
motori scollegato. Il file nuovo si recupera nella home con:

```bash
cd
cp /boot/firmware/hamda_quattro_motori.py .
python3 hamda_quattro_motori.py off
```

Queste righe vanno eseguite sul Raspberry. Prima di un'eventuale copia
successiva conservare le modifiche locali al file, se presenti.

## Procedura di prova e verifiche ulteriori

1. Controllare i collegamenti seguendo i singoli fili secondo la tabella,
   con alimentazioni scollegate. Powerbank scollegato anche durante off.
2. Solo dopo off riuscito, collegare il powerbank: i motori devono
   restare fermi. In caso di movimento inatteso o errore, scollegarlo.
3. Provare terzo e quarto separatamente, con il comando appropriato e
   osservazione dell'arresto spontaneo. Scollegare il powerbank dopo
   ciascuna prova; verificare anche i primi due sul nuovo file.
4. Verificare l'alimentazione sotto carico prima di aumentare il numero
   di motori contemporanei. La corrente reale dei motori e la capacita'
   continua effettiva del piccolo buck non sono state misurate.
   La misura a vuoto di circa 3 V non dimostra la capacita' a quattro
   motori. Il multimetro va impostato in tensione continua, non corrente
   o resistenza, per misurare in parallelo all'uscita del regolatore.
5. Il breve impulso tutti e' gia' stato provato con esito positivo.
   Prima di estendere durata o numero di motori, verificare la tensione
   sotto carico, la corrente e la temperatura del regolatore. La prova
   breve non collauda il funzionamento continuo o altri motori.

## Installazione diretta sul Raspberry

Dopo l'accesso alla rete del lavoro, Firefox mostrava un errore TLS per
Google. L'utente ha confermato data errata e mancata correzione automatica
con timedatectl set-ntp true. Le foto IMG_9179--9181 mostrano il Control
Centre e la pagina Localisation con il solo controllo del fuso orario.
L'utente ha successivamente confermato impostata manualmente la data e
ha chiesto di tornare all'aggiornamento. Non e' ancora confermato che
Firefox apra questa chat sul Raspberry o che l'orologio resti corretto
dopo il prossimo avvio.

Per copiare direttamente dal browser del Raspberry e' pronto il blocco
/workspace/exports/installa_quattro_motori_raspberry.txt. Rifiuta sistemi
diversi da Linux o privi di /dev/i2c-1; copia il nuovo programma in un
file temporaneo nella home, verifica SHA256 e compilazione, conserva
un'eventuale versione precedente del file a quattro motori, rinomina
e imposta off. Non tocca hamda_banco.py. Sintassi Bash e identita' del
sorgente incorporato verificate. Il blocco e' stato fornito all'utente,
che ha riferito il messaggio off e poi il successo del comando tutti.
La copia nella bootfs non e' necessaria per questa installazione diretta
e non e' stata dichiarata eseguita.

## Versione funzionante conservata

Archivio: /workspace/exports/HAMDA_banco_quattro_motori_2026-11-09.zip.
Contiene sorgente a quattro motori e precedente a due motori, i relativi
test, collegamenti, promemoria e installatori per Raspberry e SD dal Mac.
README e SHA256SUMS descrivono contenuti e integrita' dei file.
Il promemoria corrente e' docs/COMANDI_HAMDA.txt. Il vecchio archivio
HAMDA_banco_due_motori_2026-11-06.zip rimane conservato.
