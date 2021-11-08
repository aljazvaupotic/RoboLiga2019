# ev3-nabiralec

Demonstracijski program za robota Lego Mindstorms EV3, ki se zna premikati po danih točkah na poligonu. Namenjeno tekmovanju [Robo liga FRI 2019: Sadovnjak](https://www.fri.uni-lj.si/sl/robo-liga-fri).

Program je napisan v Python3 in deluje na operacijskem sistemu [ev3dev](https://www.ev3dev.org/).

## Priprava okolja

Sledite navodilom [ev3dev Getting Started](https://www.ev3dev.org/docs/getting-started/), da pridobite operacijski sistem `ev3dev-stretch` in ga namestite na SD kartico, ki ste jo dobili s kompletom. Za priklop v brezžično omrežje uporabite adapter za WiFi, ki ste ga prav tako dobili v kompletu.

Na robota se povežete prek protokola SSH, datoteke pa nalagate nanj prek protokola SFTP. Privzeto je uporabniško ime `robot` in geslo `maker`.

- Če uporabljate Windows, vam priporočamo uporabo programa [MobaXterm](https://mobaxterm.mobatek.net/), ki združuje odjemalca za SSH in SFTP v učinkovitem grafičnem uporabniškem vmesniku.

- Enostavnejša možnost pa je uporaba urejevalnika [Visual Studio Code](https://code.visualstudio.com/) v kombinaciji z razširitvijo [EV3 Device Browser](https://github.com/ev3dev/vscode-ev3dev-browser). Za namestitev in konfiguracijo [sledite tem izčrpnim navodilom](https://sites.google.com/site/ev3python/setting-up-vs-code).

## Namestitev potrebnih paketov

Povežite se na robota in v terminalu izvršite naslednje ukaze za namestitev paketov `pycurl` in `ujson`:

`sudo apt-get update`

`sudo apt-get install python3-pycurl`

`sudo apt-get install python3-ujson`

## Zagon programa

Na robota prenesite (SFTP) datoteko `nabiralec.py`.
V terminalu na robotu se premaknite v mapo, ki vsebuje zgornjo datoteko. Najprej dajte datoteki pravice za izvajanje:

`chmod +x nabiralec.py`

Nato lahko program poženete:

`./nabiralec.py`

## Kratek opis delovanja programa

- Ključni parametri, ki jih morate nujno nastaviti:

    ```Python
    # ID robota. Spremenite, da ustreza številki označbe, ki je določena vaši ekipi.
    ROBOT_ID = 10
    # Konfiguracija povezave na strežnik. LASPP strežnik ima naslov "193.2.72.3".
    SERVER_IP = "193.2.72.3"
    ```

- Predpostavljamo, da se datoteka `game.json`, ki hrani podatke o tekmi, nahaja v začetni (root) mapi na strežniku.

- Vzpostavitev povezave s strežnikom in pošiljanje zahteve:

    ```Python
    conn = Connection(url)
    game_state = conn.request()
    ```

- Predpostavljamo, da ste velika motorja priklopili na izhoda A in D, lahko pa to nastavite v spremenljivkah `MOTOR_LEFT_PORT` in `MOTOR_RIGHT_PORT`.

- Del programa je namenjen preverjanju, ali je dotično tipalo priklopljeno na vhod. Za zgled smo uporabili tipalo za dotik (`TouchSensor`), vendar v sami kodi nismo uporabili njegove vrednosti.

- Program na robotu izvaja premikanje po vnaprej določenih točkah na poligonu. Seznam je definiran kot `targets_list`. V našem primeru se bo robot vozil po notranjih kotih obeh košar. [Več informacij o zapisu stanja tekme](https://github.com/RoboLiga/roboliga-meta/blob/master/Tehnicna-dokumentacija/Opis-game-json.md).

    ```Python
    targets_list = [
        Point(game_state['field']['baskets'][team_my_tag]['bottomRight']),
        Point(game_state['field']['baskets'][team_my_tag]['topRight']),
        Point(game_state['field']['baskets'][team_op_tag]['topLeft']),
        Point(game_state['field']['baskets'][team_op_tag]['bottomLeft']),
    ]
    ```
- Robot izvaja štiri stanja, katerim seveda lahko dodate poljubna druga, denimo za zaznavanje bližnjega trka.
  - `IDLE`: stanje mirovanja in tudi začetno stanje. Tu se odločamo, kaj bo robot sedaj počel.
  - `LOAD_NEXT_TARGET`: kot trenutno ciljno točko naložimo naslednjo točko iz seznama `targets_list`. Ko pridemo do konca seznama, gremo spet od začetka.
  - `TURN`: stanje obračanja robota na mestu z regulatorjem PID. Hitrost levega motorja je nasprotna vrednost hitrosti desnega motorja. Stanje je zaključeno, ko je robot obrnjen proti ciljni točki v toleranci `DIR_EPS` stopinj.
  - `DRIVE_STRAIGHT`: stanje vožnje "naravnost" (robot vmes tudi zavija, da ohranja ničelno napako v kotu med sabo in ciljem). Hitrost na motorju je sestavljena iz dveh delov: nazivna hitrost (base) in hitrost obračanja (turn). Vsaka od njih je podvržena regulaciji s svojim regulatorjem PID.

- Robot miruje, če tekma ne teče (`game_state['gameOn'] == False`) ali če oznaka robota ni zaznana.

- Za nastavitev hitrosti obeh motorjev uporabljamo regulator PID (sestavljen iz Proporcionalnega, Integralnega in oDvodnega člena), ki je določen z naslednjimi parametri:
  - `Kp`: ojačitev proporcionalnega dela regulatorja. Visoke vrednosti pomenijo hitrejši odziv sistema, vendar pozor: previsoke vrednosti povzročijo oscilacije in nestabilnost.
  - `Ki`: ojačitev integralnega člena regulatorja. Izniči napako v ustaljenem stanju. Zmanjša odzivnost.
  - `Kd`: ojačitev odvoda napake. Zmanjša čas umirjanja in poveča odzivnost.
  - `integral_limit`: najvišja dovoljena vrednost integrala. Sčasoma namreč lahko integralni člen zelo naraste in ga je modro omejiti.
  
  Povabljeni ste, da preizkušate različne nastavitve teh parametrov in s tem dosežete boljši (hitrejši/stabilnejši) odziv.

## Priporočeni viri

- [Uradna stran projekta ev3dev](https://www.ev3dev.org/)

- [Vodiči za programiranje EV3 v Pythonu](https://sites.google.com/site/ev3python/)

- [Dokumentacija knjižnice `python-ev3dev`](https://ev3dev-lang.readthedocs.io/projects/python-ev3dev/en/stable/)
