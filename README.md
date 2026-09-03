# Contrôle de la voiture via interface web

## Installation sur le Raspberry Pi

```bash
pip3 install -r requirements.txt
```

> Note : sur certains Raspberry Pi OS récents, il faut ajouter `--break-system-packages` :
> `pip3 install -r requirements.txt --break-system-packages`

Si `opencv-python` est lent à s'installer/compiler sur le Pi, tu peux utiliser à la place :
```bash
sudo apt install python3-opencv
```

Pour la diffusion du son du micro (voir plus bas), `ffmpeg` (qui fournit `ffplay`) doit être installé :
```bash
sudo apt install ffmpeg
```

Pour la gestion des périphériques Bluetooth, `bluetoothctl` (fourni par `bluez`) doit être installé,
et pour que la connexion à un appareil audio bascule automatiquement la sortie son, PulseAudio (ou
PipeWire) avec le support Bluetooth doit être présent :
```bash
sudo apt install bluez pulseaudio pulseaudio-module-bluetooth
```

## Lancement

```bash
python3 app.py
```

Puis, depuis n'importe quel appareil sur le même réseau (téléphone, ordinateur), ouvre un navigateur à l'adresse :

```
https://<adresse-ip-du-raspberry>:5000
```

(Trouve l'adresse IP du Pi avec `hostname -I`)

Le serveur utilise un certificat **auto-signé** (nécessaire pour que le micro fonctionne, voir plus bas) :
le navigateur affiche un avertissement « connexion non privée / non sécurisée » à la première visite.
C'est normal sur un réseau local — clique sur « Avancé » puis « Continuer/Accepter le risque » pour poursuivre.
Cet avertissement doit être accepté sur chaque appareil qui se connecte à l'interface.

## Fonctionnement

- La webcam (`/dev/video0`) s'affiche en haut de la page en flux vidéo continu (MJPEG).
- **Broches GPIO** : les 4 broches qui pilotent les moteurs sont définies en variables tout en haut de
  [app.py](app.py) (`PIN_RIGHT_FORWARD`, `PIN_RIGHT_BACKWARD`, `PIN_LEFT_FORWARD`, `PIN_LEFT_BACKWARD`).
  Elles peuvent aussi être modifiées directement depuis l'interface web (section « Broches GPIO »),
  sans redémarrer le serveur. Un bouton « Tester » à côté de chaque broche l'active seule pendant
  ~0,7s, pour vérifier le câblage de chaque roue indépendamment (il teste la broche actuellement
  enregistrée : enregistre d'abord un changement avant de le tester).
- **Déplacement** : un pavé directionnel (avancer / reculer / gauche / droite / stop) contrôle la voiture.
  Chaque bouton fonctionne en maintien (appui = actif, relâchement = arrêt), à la souris comme au doigt.
  - Avancer : avant droite + avant gauche
  - Reculer : arrière droite + arrière gauche
  - Tourner à droite : avant gauche + arrière droite
  - Tourner à gauche : avant droite + arrière gauche
- **Clavier** : par défaut, `Z` avance, `S` recule, `Q` tourne à gauche, `D` tourne à droite. Depuis la
  section « Touches du clavier », on peut réassigner n'importe quelle touche à chacune de ces actions ;
  le choix est mémorisé dans le navigateur (`localStorage`).
- **Microphone** : le bouton « Activer le micro » capture le micro de l'appareil connecté à l'interface web
  et envoie le son en continu au Raspberry Pi, qui le rejoue sur sa sortie audio par défaut via `ffplay`.
  Cela nécessite d'accéder à l'interface en **HTTPS** (voir Lancement) : les navigateurs bloquent
  silencieusement l'accès au micro sur une origine HTTP autre que `localhost`.
- **Bluetooth** : la section « Bluetooth » gère **tous** les périphériques Bluetooth du Raspberry Pi
  (enceintes, casques, manettes, etc.), pas seulement l'audio. Elle permet de lancer une recherche
  (~20s, pour laisser le temps aux appareils classiques comme les enceintes d'être détectés et nommés),
  jumeler, connecter/déconnecter ou oublier un appareil, directement depuis l'interface web. Si un
  appareil n'apparaît pas dans la recherche (par exemple parce qu'il n'est plus en mode appairage), il
  peut être ajouté directement par son adresse MAC via le champ dédié en bas de la section. Se connecter
  à une enceinte/un casque Bluetooth bascule automatiquement la sortie audio du Raspberry Pi vers cet
  appareil (voir Notes techniques).
- L'interface est responsive et utilisable aussi bien sur ordinateur que sur téléphone.

## Notes techniques

- Le flux caméra utilise OpenCV (`cv2.VideoCapture`) avec le backend V4L2 pour lire `/dev/video0`.
- Le serveur écoute sur toutes les interfaces (`0.0.0.0:5000`) pour être accessible depuis d'autres appareils.
- Le son du micro est envoyé par le navigateur en `audio/webm;codecs=opus` (API `MediaRecorder`), reçu par
  Flask puis transmis directement à un processus `ffplay` qui le joue en direct.
- À l'arrêt du serveur (Ctrl+C), les moteurs sont coupés, le GPIO est proprement libéré, la caméra est
  relâchée et le flux audio éventuel est arrêté.
- La gestion Bluetooth s'appuie sur les commandes « one-shot » de `bluetoothctl` (pas de démon supplémentaire).
  Le jumelage se fait avec l'agent `NoInputNoOutput` (accepte automatiquement les demandes de type « Just
  Works », le cas le plus courant pour les enceintes/casques) ; un appareil demandant une confirmation
  manuelle (code à saisir) ne pourra pas être jumelé depuis l'interface.
- Lors d'une connexion Bluetooth réussie, le serveur tente de basculer la sortie audio par défaut vers ce
  périphérique via `pactl` (PulseAudio/PipeWire). Si `pactl` est absent, la connexion Bluetooth fonctionne
  quand même mais la bascule audio doit être faite manuellement.
- Au démarrage, le serveur tente de débloquer l'adaptateur Bluetooth (`rfkill unblock bluetooth`) et de
  l'allumer (`bluetoothctl power on`), au cas où il serait désactivé par défaut sur le système.
- Le serveur écoute en HTTPS avec un certificat auto-signé généré à chaque démarrage (`ssl_context="adhoc"`,
  nécessite le paquet `pyopenssl`). C'est uniquement pour satisfaire les navigateurs (accès au micro) ; ça
  n'apporte pas de sécurité réelle contre quelqu'un sur le même réseau local.
