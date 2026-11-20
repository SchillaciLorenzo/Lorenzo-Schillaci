> Documentazione storica del banco PCA9685/DRV. Per la cintura con due ESP32-C3 USB leggere lo [stato attuale](STATO_2026-11-20.md).

# HAMDA: banco locale con monitor, 6 novembre 2026

Questo documento conserva la configurazione del banco a due motori.
Il 9 novembre l'ampliamento a quattro motori e' stato installato e
l'utente ha confermato il funzionamento della prova simultanea.
La versione attuale e' descritta in quattro_motori_raspberry.md;
il programma attuale e' tools/hamda_quattro_motori.py.

L'utente ha scelto di proseguire direttamente sul Raspberry, con monitor
e tastiera USB, mettendo da parte la diagnosi SSH. Non richiedere nuovi
tentativi di rete come prerequisito delle prove di banco. La foto
IMG_9130 conferma il login locale lorenzoschillaci@HAMDA e un desktop
grafico. I2C e' abilitato; /dev/i2c-1 e' presente e lorenzoschillaci
appartiene al gruppo i2c. Il programma e' stato trasferito e l'utente ha
confermato il funzionamento dei comandi singoli e della prova simultanea.

## Nuovo programma autonomo

`tools/hamda_banco.py` contiene l'intera prova in un file e usa solo la
libreria standard Python. Non importa i programmi precedenti, conservati
negli archivi prima della reinstallazione. Il programma e' sulla SD e
nella home del Raspberry. La copia sulla SD ha superato la verifica
SHA256; le prove reali descritte qui sono state confermate dall'utente.

| Comando | Effetto previsto |
| --- | --- |
| off | Imposta le uscite spente |
| primo | Impulso nominale di 0,25 s, PCA uscita 0 |
| secondo | Impulso nominale di 0,25 s, PCA uscita 1 |
| insieme | Impulso nominale di 0,25 s su entrambe |

PCA a indirizzo 0x40, bus /dev/i2c-1. Nessuna regolazione di intensita' o
frequenza in questa fase. FULL_ON/FULL_OFF realizzano il comando digitale;
l'alimentazione dei motori resta quella del convertitore a circa 3 V.

Il codice tenta lo spegnimento su tutte le 16 uscite, anche se una singola
scrittura fallisce, e verifica il registro OFF_H delle uscite 0 e 1.
In caso di errore segnala l'arresto non confermato. SIGINT, SIGTERM e
SIGHUP attivano la pulizia; il lock e' condiviso con i vecchi programmi.
Questo non misura il movimento o la corrente e non garantisce l'arresto
in caso di guasto I2C persistente, SIGKILL o blocco del sistema. Prove
sorvegliate con disconnessione fisica del powerbank accessibile.

## Percorso operativo locale

1. PCA e powerbank dei motori ancora scollegati. Sul Raspberry leggere:
   `ls -l /dev/i2c-1` e `id -nG`. Fotografare il risultato se si lavora
   dal monitor, senza trasferimento appunti dal Mac.
2. Per trasferire il programma senza rete, spegnere correttamente il
   Raspberry, poi scollegarne l'alimentazione e portare la SD nel lettore
   Mac. Copiare il solo hamda_banco.py nella bootfs: nessuna nuova
   scrittura del sistema operativo o modifica dei file di avvio.
3. Espellere bootfs dal Mac; riportare la SD nel Raspberry. Prima di
   alimentare, ricollegare la PCA con i quattro fili I2C/alimentazione
   logica, seguendo foto e istruzioni guidate. Powerbank motori scollegato.
4. Avviare con USB-C POWER IN, monitor acceso su HDMI0 e tastiera USB.
   Nel Terminale locale eseguire una riga alla volta:

   ```bash
   cd
   cp /boot/firmware/hamda_banco.py .
   python3 hamda_banco.py off
   ```

5. Solo dopo verifica del cablaggio e del comando off, collegare il
   powerbank dei motori: devono restare fermi. Provare prima il comando
   primo, poi secondo, osservando selezione corretta e arresto spontaneo.
   Scollegare il powerbank dopo ciascuna prova. Provare insieme solo dopo
   il successo dei due comandi indipendenti.

## Cablaggio di riferimento

- Pi pin fisico 1 (3,3 V) verso PCA VCC; pin 3 SDA verso SDA;
  pin 5 SCL verso SCL; pin 6 GND verso GND.
- PCA giallo uscita 0 verso DRV IN1, IN2 verso negativo comune.
- PCA giallo uscita 1 verso DRV IN3, IN4 verso negativo comune.
- PCA nero verso negativo comune della breadboard/DRV/convertitore.
- Pin rossi V+ PCA e morsetto verde PCA liberi.
- DRV OUT1/OUT2 verso motore 1; OUT3/OUT4 verso motore 2; FAULT libero.
- DRV VCC/SLEEP al positivo motori circa 3 V; DRV GND al negativo.

Il precedente errore dell'uscita 1 era stato riferito come corretto:
IN3 inizialmente libero, poi collegato per errore al nero della PCA mentre
il giallo finiva al negativo. L'utente ha dichiarato di aver scambiato i
due attacchi. Durante le nuove prove l'utente ha nuovamente riferito un
problema sul secondo motore, poi ha dichiarato funziona tutto e ha
confermato anche la prova simultanea. Non e' stata documentata una causa
specifica del problema. La descrizione dei collegamenti e il risultato
funzionale non sostituiscono una foto completa del montaggio attuale.

## Verifiche del nuovo file nel workspace

Otto test con bus simulato superati: spegnimento prima della
configurazione, selezione indipendente/insieme con impulso nominale
limitato, pulizia dopo interruzione, conferma I2C persa durante
attivazione, prosecuzione dell'arresto dell'altro canale dopo errore sul
primo, rilevamento di un arresto ignorato, rifiuto del clock esterno e
blocco concorrente con ripristino dei gestori dei segnali.

```bash
python3 -m unittest discover -s tests -p test_banco_locale.py -v
```

Il blocco da eseguire sul Mac per copiare il solo programma nella SD e'
/workspace/exports/copia_hamda_banco_su_sd_mac.txt. Sorgente incorporato
identico a tools/hamda_banco.py e sintassi Bash verificati. Trasferimento,
accesso I2C e prove al banco sono stati successivamente completati come
riportato nei paragrafi seguenti.

## Primo controllo locale completato

L'utente ha mostrato /dev/i2c-1 come dispositivo a caratteri, proprietario
root, gruppo i2c e permessi crw-rw----. Il risultato di id -nG include
i2c, sudo e gpio per lorenzoschillaci. Il bus I2C e l'accesso del normale
utente sono quindi disponibili. La riga iniziale di puntini terminata
con command not found e' un comando estraneo; i due controlli successivi
sono riusciti.

Per il trasferimento e' stato indicato di spegnere localmente con
sudo systemctl poweroff, attendere 30 secondi, scollegare POWER IN e
spostare la SD nel lettore del Mac. E' stato trasferito soltanto il
programma, senza riscrivere il sistema o applicare i vecchi preparatori
Ethernet/seriale.

## Trasferimento del programma confermato

L'utente ha eseguito il blocco di copia sul Mac e ha mostrato sia
Integrita' del programma verificata sia Programma hamda_banco.py copiato
sulla SD. Il file /Volumes/bootfs/hamda_banco.py corrisponde quindi al
sorgente verificato, SHA256
40b154fd05e123b5bbcf1b065556fad713d4e7e973eac8e72cbdb85cafe0a53f.
Le successive prove reali sono riportate sotto.

Dopo il completamento l'utente ha incollato anche il testo della conferma
al prompt del Mac, aprendo una citazione incompleta e ottenendo il prompt
secondario >. La sequenza incompleta e' stata interrotta con Control+C;
non era necessario ripetere il trasferimento. L'utente ha successivamente
riferito di aver ricollegato l'hardware e ha completato le prove.

## Prime prove reali del nuovo programma

L'utente ha dichiarato ricollegata la PCA. Ha inizialmente eseguito i
comandi di copia sul Mac, ottenendo file non trovato; e' stato guidato a
usare il Terminale locale del Raspberry, verificando hostname HAMDA.
Ha poi confermato il messaggio del comando off. Dopo il collegamento del
powerbank, il comando python3 hamda_banco.py primo e' stato provato sul
banco: alla domanda se avesse vibrato il primo motore e si fosse fermato
da solo ha risposto si, ha funzionato. La durata meccanica non e' stata
misurata; l'impulso software impostato resta 0,25 s.

La prova reale del primo motore con il nuovo file e' quindi riuscita.

Successivamente il secondo motore era stato riferito come fermo.
L'utente ha descritto giallo PCA verso IN3, nero verso negativo comune,
OUT3/OUT4 verso il secondo motore e ha confermato IN4 al negativo.
Alla richiesta di foto per verificare l'uscita PCA e l'esito del comando
ha poi risposto funziona tutto. Registrare questa come conferma generale
di funzionamento dell'utente, senza attribuire una causa accertata al
problema precedente o una modifica specifica non documentata.
Alla successiva richiesta di eseguire python3 hamda_banco.py insieme,
osservare la vibrazione di entrambi e l'arresto spontaneo, l'utente ha
risposto si funziona. La prova contemporanea e l'arresto sono quindi
confermati dall'utente. Non e' stata misurata la durata meccanica o la
corrente dei motori e non sono stati collaudati piu' di due motori.

## Passo successivo

Il 9 novembre, dopo uno scollegamento improvviso e il ritorno al login
locale del Raspberry, l'utente ha ripetuto la prova simultanea e ha
riconfermato che tutto funziona. Ha poi chiesto un foglio per conservare
i comandi importanti, precisando di usare il Mac. Il promemoria e'
docs/COMANDI_HAMDA.txt: si conserva e si modifica sul Mac con TextEdit,
mentre i comandi del banco si eseguono sul Raspberry. Non occorre
spostare la SD o riprendere la configurazione SSH per creare il foglio.

Conservare questa versione funzionante. Prima di ampliare il banco,
scollegare il powerbank dei motori, spegnere correttamente il Raspberry
e togliere la sua USB-C. Fotografare il montaggio attuale e il regolatore
da circa 3 V, dal lato dei collegamenti, per documentare la configurazione
e individuare gli attacchi ancora provvisori. Non assumere che i vecchi
VIN temporanei siano tuttora presenti o che siano gia' stati saldati:
lo stato meccanico attuale deve essere osservato.
