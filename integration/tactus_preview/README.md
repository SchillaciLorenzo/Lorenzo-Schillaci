> Archivio della preview offline del 18 novembre. Il banco corrente a due ESP USB è documentato nel [README principale](../../README.md). Questa preview non è collegata ai motori.

# Prima base offline per HAMDA e TACTUS

Preparata il 18 novembre 2026 dai tre file TACTUS forniti dall'utente.
Questa e' una **simulazione dei comandi**, non il programma che pilota
gia' il banco: non apre rete, MQTT o I2C e non muove i motori.
Non importa i programmi originali, che avviano servizi all'importazione.

## Cosa verifica

- Riceve lo stato davanti/destra/dietro/sinistra per unita'.
- Accetta i valori JSON true/false e le stringhe "true"/"false".
- Produce livelli 0/255, come il dataHandler TACTUS corrente.
- Instrada le posizioni ai canali locali 0--3 oppure a messaggi MQTT
  con formato `<prefisso>/pin/<indice>` secondo una tabella esplicita.
- Controlla l'intero messaggio prima di produrre un risultato: valori
  malformati e destinazioni ambigue non generano piani parziali.
- Nella semantica di questa preview, posizioni/unita' assenti significano
  spento. Prima del collegamento live verificare che il produttore Unreal
  invii lo stato completo, non soltanto gli eventi cambiati.

Il numero 255 nel piano locale e' un livello logico di anteprima, non
un valore da scrivere direttamente nei registri della PCA. Il futuro
backend dovra' tradurlo in un'azione hardware appropriata, rispettando
il collaudo attuale limitato a impulsi nominali di 0,25 secondi.

## Esecuzione della demo

Da questa cartella, con Python 3:

```bash
python3 tactus_bridge_preview.py --demo
```

Sono sufficienti i moduli standard Python. La demo legge demo_routes.json:
unita', posizioni e indici sono esempi fittizi. Il prefisso remoto
`remote_demo_UNCONFIRMED` non identifica un dispositivo TACTUS verificato.
La mappa 0/1/3/4 e' soltanto un esempio configurabile: non prova il
cablaggio della prima unita' e non corregge automaticamente il software.

## Messaggi propri

Preparare un file di configurazione con local_units e remote_units e
un file JSON di ingresso. Poi usare:

```bash
python3 tactus_bridge_preview.py --config configurazione.json --frame ingresso.json
```

Anche questa modalita' stampa soltanto il piano. In alternativa, con
--config, il frame puo' essere letto dallo standard input. Gli ingressi
CLI sono limitati a 64 KiB per file/messaggio e devono essere UTF-8.

## Verifica automatica

```bash
python3 -m unittest discover -s . -p test_tactus_bridge_preview.py -v
```

36 test superati: instradamento locale/remoto, stati e booleani,
assenza di dati, mappe esplicite, validazione atomica, conflitti di
destinazione, JSON ambiguo e demo senza dipendenze esterne.
Questi risultati non sono un collaudo della cintura o della rete.

## Prima della prova reale

Servono Raspberry e una sola unita' TACTUS identificata. Verificare
rete e broker previsti dagli ESP, nome effettivo dell'unita', significato
dei suffissi /pin, mappa fisica dei motori e comando di abilitazione.
Il comando globale vibrationActive non compare nei tre file Python
forniti; non se ne puo' inventare un topic o un payload.

Il programma live richiedera' gestione di STOP e tempi massimi, errori
di connessione, perdita di dati, messaggi MQTT non persistenti e client
distinti. L'eventuale protezione del solo computer non puo' garantire
l'arresto di un ESP irraggiungibile: il suo firmware va verificato.
Le istruzioni segnalano anche possibili vibrazioni all'accensione.

Il banco HAMDA funzionante e il suo programma a quattro motori restano
conservati separatamente. Nessuno dei file di questa cartella e' stato
installato sul Raspberry dell'utente o inviato al repository ESA.
