> Documentazione storica del banco PCA9685/DRV. Per la cintura con due ESP32-C3 USB leggere lo [stato attuale](STATO_2026-11-20.md).

# Ripristino Raspberry HAMDA, 5 novembre 2026

L'utente ha autorizzato esplicitamente la reinstallazione di Raspberry
Pi OS sulla microSD, sapendo che ne cancella il contenuto, e desidera
ricreare i programmi dopo il ripristino. Non occorre richiedere di nuovo
questa autorizzazione. Verificare il dispositivo di destinazione prima
della scrittura: solo la microSD del Raspberry, in precedenza identificata
come Generic MassStorageClass Media, circa 63,9 GB.

## Cosa conserviamo

L'archivio di recupero conserva i sorgenti del workspace dei due programmi
di prova, i test, gli installatori e i resoconti del banco. Non e' stata
letta un'immagine completa della microSD e non e' disponibile l'accesso
SSH per copiarne la home attuale. La copia del primo programma dal
Raspberry al Mac era gia' riuscita al 100%, con destinazione:

`~/Downloads/HAMDA_primo_motore_2026-11-05.py`

Il primo motore aveva vibrato e si era fermato da solo. Il programma per
due motori aveva completato i comandi senza errori; l'utente aveva provato
motori e cavetti attraverso OUT1/OUT2. Il secondo ponte e il secondo
comando PCA non hanno ancora superato una prova reale. Vedere il
resoconto aggiornato `due_motori_raspberry.md`.

## Preparazione fisica

1. Scollegare il powerbank dei motori.
2. Scollegare la USB del Raspberry; SSH non e' attualmente disponibile
   per lo spegnimento. Evitare di ripetere riavvii senza uno scopo preciso.
3. Se ancora presenti, fotografare e staccare i quattro cavetti Pi-PCA
   dal lato PCA, lasciando in posizione quelli sul Raspberry. Tutte le
   modifiche ai cavetti si fanno senza alimentazione.
4. Estrarre la microSD solo quando il Raspberry e' senza alimentazione.
   Inserirla nel lettore collegato al Mac.

## Nuova installazione prevista

Usare Raspberry Pi Imager sul Mac, gia' disponibile nella versione 2.0.12.

| Campo | Valore previsto |
| --- | --- |
| Dispositivo | Raspberry Pi 4 |
| Sistema | Raspberry Pi OS Lite (64-bit), versione stabile disponibile |
| Archiviazione | La microSD del Raspberry, circa 64 GB |
| Hostname | HAMDA, maiuscolo scelto dall'utente |
| Utente | lorenzoschillaci, tutto minuscolo |
| Password | Scelta e conservata dall'utente; non inviarla nella chat |
| Localizzazione | Lingua, tastiera e fuso effettivi dell'utente |
| SSH | Abilitato con autenticazione tramite password |
| Wi-Fi | Non necessario per il collegamento USB previsto |
| Raspberry Pi Connect | Lasciare disabilitato per questa prova locale |

Lite riduce i componenti avviati e non richiede un desktop. La nuova
installazione serve a ricreare una configurazione verificabile; la causa
precedente potrebbe anche riguardare cavo, alimentazione o connessione
USB, e non e' ancora stata accertata.

Dopo scrittura e verifica di Imager, mantenere la microSD nel Mac:
prima del primo avvio va preparato anche il collegamento di rete USB.
L'abilitazione SSH da sola non crea la rete tra Mac e Raspberry.

## Collegamento USB da ricreare e verificare

La configurazione che aveva consentito l'accesso usava:

- Pi USB-C verso il Mac con cavo dati; Pi alimentato dal Mac.
- `dtoverlay=dwc2,dr_mode=peripheral` nella sezione globale di config.txt.
- `modules-load=dwc2,g_ether` nella singola riga di cmdline.txt.
- MAC Pi 02:48:41:4d:44:01 e MAC lato Mac 02:48:41:4d:44:02.
- IP Pi 10.55.0.2/24 e IP Mac 10.55.0.1/24, senza router su questa rete.
- La nuova immagine dovra' essere ispezionata per scegliere il metodo di
  configurazione persistente della rete, evitando profili concorrenti.

Gli script USB precedenti conservati come riferimento non rappresentano
da soli una procedura completa per qualunque nuova immagine: il vecchio
prepare_hamda_usb_network_mac.sh richiede gia' config.txt e cmdline.txt
modificati e riscrive soltanto network-config.

Al primo accesso riuscito verificare il profilo NetworkManager attivo e
la sua persistenza. Completare almeno uno spegnimento dal Raspberry e un
nuovo avvio con accesso USB riuscito prima di ricollegare PCA e motori.

La reinstallazione cambia le chiavi host SSH: confrontare l'eventuale
avviso con il ripristino appena effettuato e aggiornare soltanto le
vecchie voci HAMDA del Mac, mantenendo le altre chiavi conosciute.

## Ripresa delle prove

1. Raspberry da solo: avvio, rete USB e SSH stabili dopo riavvio.
2. I2C abilitato; PCA collegata senza alimentazione motori; rilevamento
   dell'indirizzo 0x40, con possibile alias All Call 0x70.
3. Ricreare il programma di prova e verificarne le uscite spente.
4. Provare il primo motore con un impulso breve e arresto osservato.
5. Verificare e provare il secondo comando e motore separatamente.

L'utente ha dichiarato completate scrittura e verifica con Imager, dopo
aver impostato hostname HAMDA, mantenuto l'utente lorenzoschillaci,
abilitato SSH con password e lasciato Raspberry Pi Connect disabilitato.
La nuova microSD deve restare nel Mac per ispezionare i file di avvio e
preparare USB prima del primo avvio. La nuova immagine e il collegamento
USB non sono ancora stati verificati tramite i risultati dei comandi.

## Ispezione e nuovo preparatore USB

L'utente ha poi mostrato i file della nuova bootfs: sono presenti
`user-data`, `meta-data` e `network-config`. La cmdline e' su una sola
riga e usa `root=PARTUUID=9586d7bf-02` e
`ds=nocloud;i=rpi-imager-1793895500719`; non contiene ancora moduli USB
gadget. Questi identificativi devono restare quelli della nuova immagine.

E' stato preparato `tools/configura_usb_mac.py`, esportato come blocco
da incollare in `/workspace/exports/configura_usb_nuova_sd_mac.txt`.
Il preparatore deve essere eseguito sul Mac con bootfs montata; conserva
user-data e meta-data, salva gli altri tre originali nella cartella
`hamda-before-usb`, aggiunge la configurazione globale dwc2, integra
g_ether nella cmdline senza sostituire root o l'identificativo NoCloud,
e scrive la rete USB con MAC fisso, nome usb0 e indirizzo 10.55.0.2/24.

Cinque test su directory temporanee sono riusciti: preservazione di
identificativi e credenziali, ripetibilita' con backup originale intatto,
rifiuto di file cloud-init mancanti, rifiuto di cmdline invalida e gestione
dei moduli esistenti/conflittuali. YAML e sintassi del blocco verificati.
L'utente ha eseguito il blocco sul Mac e ha mostrato i messaggi di esito:
SD preparata per USB, originali in /Volumes/bootfs/hamda-before-usb,
account Imager conservato e indirizzi previsti 10.55.0.2 / 10.55.0.1.
Il nuovo avvio reale e la rete devono ancora essere verificati, compreso
un successivo spegnimento corretto e riavvio prima di ricollegare la PCA.

## Primo controllo dopo la nuova preparazione

L'utente ha mostrato Raspberry Pi USB Gadget su en7 con MAC host previsto.
ifconfig en7 ha pero' restituito status inactive, senza indirizzi IPv4 o
IPv6. Un successivo system_profiler ha rilevato il gadget USB Raspberry Pi
Ltd., VID 0x2e8a / PID 0x0013, velocita' fino a 480 Mb/s e Location ID
0x14300000 / 3. La presenza USB e' quindi osservata anche mentre la rete
e' inattiva; la causa della mancata attivazione non e' ancora accertata.

E' stato preparato il blocco /workspace/exports/configura_rete_usb_mac.txt:
controlla il MAC di en7, abilita il servizio USB, assegna l'indirizzo
persistente lato Mac 10.55.0.1/24, riallinea l'indirizzo corrente e stampa
stato, percorso e ping. Si esegue sul Mac, con password amministratore del
Mac; non cambia Wi-Fi o altre interfacce. L'utente lo ha eseguito: en7 ha
ottenuto 10.55.0.1/24 e il percorso e' diventato en7, ma lo stato resta
inactive e il ping ha perso tutti e quattro i pacchetti. Non ripetere
assegnazioni di IP come unica diagnosi: serve osservare il Raspberry.

## Possibile accesso diagnostico senza monitor

L'utente e' a casa senza monitor/cavo micro-HDMI/tastiera USB; li ha al
lavoro. Preparato tools/prepara_console_usb_mac.py per tentare una
console seriale USB usando g_serial e serial-getty@ttyGS0.service.
La modifica e' temporanea e conserva esattamente la cmdline Ethernet
nel backup cmdline.txt.hamda-ethernet. Non modifica gli account o le
password e richiede il normale login del Raspberry. Durante questa
prova il gadget non offre la rete Ethernet: en7 non e' il test da usare.
La sola configurazione di rete cloud-init viene disabilitata per il boot
diagnostico tramite network-config=disabled; il resto di cloud-init resta
abilitato per completare la creazione dell'account se necessario.

La disponibilita' del modulo g_serial e il login sul banco reale non
sono stati ancora verificati. Prima di applicare la modifica, riportare
la SD nel Mac solo dopo aver tolto alimentazione al Raspberry, e
verificare che sul Mac sia disponibile screen. Dopo la modifica e il
nuovo avvio identificare il dispositivo /dev/cu.usbmodem... prima di
aprire screen; non inventarne il nome.

Per ripristinare la configurazione di boot Ethernet si puo' usare la
funzione restore_ethernet del preparatore sul Mac o, da una sessione
locale del Raspberry, copiare con sudo il backup
/boot/firmware/cmdline.txt.hamda-ethernet su /boot/firmware/cmdline.txt.
Prima del riavvio verso Ethernet verificare e rendere persistente la
configurazione effettiva NetworkManager sul Raspberry, con MAC device
02:48:41:4d:44:01 e indirizzo 10.55.0.2/24.

Il Mac ha confermato la disponibilita' di /usr/bin/screen. Il preparatore
console richiede soltanto cmdline.txt e config.txt, per funzionare anche
se la nuova immagine avesse rimosso i file seed dopo il primo avvio.
Cinque verifiche su file temporanei sono superate, incluse conservazione
degli account, backup, ripetibilita' e ripristino byte per byte della
cmdline Ethernet. Il blocco e' esportato in
/workspace/exports/prepara_console_usb_mac.txt. La modifica reale sulla
SD e il successivo rilevamento della porta seriale non sono ancora
stati confermati dall'utente.

## Monitor al lavoro, 6 novembre 2026

L'utente e' tornato al lavoro e ha trovato un cavo micro-HDMI verso HDMI.
Il monitor Dell, dopo aver ricevuto la propria alimentazione, mostra
No HDMI signal from your device. Le foto IMG_9124 e IMG_9125 confermano
il messaggio. IMG_9127 mostra la scheda con GPIO scollegati e micro-HDMI
in HDMI0, la presa piu' vicina alla USB-C. In questa foto la presa USB-C
POWER IN e' vuota, mentre e' occupata una porta USB-A con un cavo nero
di cui non si vede l'altra estremita'. Non e' noto se l'alimentazione
sia stata scollegata soltanto per la foto; non dedurre da questo lo
stato di tutte le prove precedenti.

Il prossimo controllo fisico e' avviare con monitor gia' acceso e ingresso
HDMI corretto, SD inserita, alimentazione nella presa USB-C POWER IN e
senza il cavo USB-A non identificato. Poi si potra' collegare la tastiera
USB identificata. Evitare altre modifiche della SD prima di chiarire
l'effettivo collegamento dell'alimentazione.

## Accesso locale e rete USB osservati, 6 novembre 2026

Dopo le istruzioni per collegare POWER IN, l'utente ha riferito di essere
entrato nel sistema. IMG_9130 mostra un desktop grafico con Terminale
locale e prompt lorenzoschillaci@HAMDA. L'immagine attualmente avviata
dispone quindi di un desktop: non presumere che sia Lite e non richiedere
una nuova reinstallazione soltanto per questo.

Nella parte finale della foto i comandi corretti hanno restituito:

- nmcli device status: usb0 ethernet connected, connessione netplan-usb0;
- ip -br address: usb0 UP, IPv4 10.55.0.2/24, IPv6 link-local
  fe80::48:41ff:fe4d:4401/64; eth0 e wlan0 DOWN;
- /proc/cmdline: modules-load=dwc2,g_ether, MAC device e host previsti,
  identificativo NoCloud rpi-imager-1793895500719.

Non sono presenti i parametri g_serial/network-config=disabled previsti
dall'alternativa seriale: non continuare ad applicare il preparatore
console, dato che ora l'interfaccia Ethernet sul Raspberry e' connessa.
Il prossimo passo e' controllare il ping dal Mac e riaprire SSH. Il
successo di ping e SSH dal Mac non e' ancora confermato dopo questi
risultati locali.

Aggiornamento: il successivo ping dal Mac a 10.55.0.2 ha ricevuto quattro
risposte su quattro, perdita 0%, tempi circa 0,9-1,4 ms. Il vecchio ping
fallito presente prima nel testo incollato e' storico; considerare
l'ultimo risultato riuscito. Si procede alla riapertura SSH come
lorenzoschillaci; essendo stata reinstallata la SD, aggiornare soltanto
la vecchia voce 10.55.0.2 in known_hosts del Mac. Accesso SSH dopo il
ripristino e successivo avvio senza monitor ancora da confermare.

SSH dopo il ripristino confermato il 6 novembre: l'utente ha rimosso
soltanto 10.55.0.2 dai known_hosts del Mac, ha accettato la nuova chiave
ED25519 SHA256:RyA1pUbxCOISIQSViguLGAhBj/lE54Ii3V1p/no2LQ4 e ha
effettuato il login con password come lorenzoschillaci. Il banner mostra
Linux HAMDA 6.18.50+rpt-rpi-v8 e il prompt atteso. Non rimuovere di nuovo
questa chiave per un semplice riavvio della medesima installazione.

I vecchi programmi di banco restano negli archivi del workspace e nella
precedente copia del primo script sul Mac; la loro presenza sulla SD
nuova non e' stata accertata. Non eseguire comandi che li presuppongono
installati. L'utente vuole ricreare i programmi dopo il ripristino.
Prossimo passo: abilitare I2C nella sessione SSH del Raspberry, spegnere
correttamente, rimuovere monitor/tastiera a scheda senza alimentazione,
e confermare un nuovo accesso USB/SSH con solo Mac e Raspberry. La SD
resta nel Raspberry; PCA e motori ancora scollegati. Poi ricreare e
collaudare il programma di banco per un motore e successivamente due.

Il tentativo di rientro dopo lo spegnimento ha dapprima subito il noto
errore di incolla 00~ sul Bash del Mac; una nuova finestra ha poi eseguito
SSH correttamente ma ha ricevuto timeout. La causa del mancato accesso
dopo riavvio non e' stata accertata e non e' confermata la persistenza
senza monitor. L'utente e' entrato localmente, ha riferito un indirizzo
wlan e ha infine chiesto esplicitamente di lasciare da parte SSH per
continuare il progetto con il secondo monitor. Questa e' la modalita'
operativa attuale: seguire docs/banco_locale_due_motori.md, senza
richiedere ulteriori prove SSH come prerequisito. Per il codice nuovo
e' previsto trasferimento tramite SD e lettore Mac gia' disponibili.

Il PARTUUID root osservato dopo l'avvio differisce da quello precedente
al primo avvio: non sovrascrivere la cmdline attuale con backup creati
prima del primo avvio senza preservare il root= attualmente funzionante.
Per mantenere accesso senza schermo servono ancora verifica del profilo
persistente, spegnimento corretto e un nuovo avvio USB riuscito prima di
ricollegare PCA e motori.
