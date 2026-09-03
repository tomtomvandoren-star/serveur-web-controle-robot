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
et pour que la connexion à un appareil bascule automatiquement la sortie audio, PulseAudio (ou
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
http://<adresse-ip-du-raspberry>:5000
```

(Trouve l'adresse IP du Pi avec `hostname -I`)

## Fonctionnement

- La webcam (`/dev/video0`) s'affiche en haut de la page en flux vidéo continu (MJPEG).
- **Broches GPIO** : les 4 broches qui pilotent les moteurs sont définies en variables tout en haut de
  [app.py](app.py) (`PIN_RIGHT_FORWARD`, `PIN_RIGHT_BACKWARD`, `PIN_LEFT_FORWARD`, `PIN_LEFT_BACKWARD`).
  Elles peuvent aussi être modifiées directement depuis l'interface web (section « Broches GPIO »),
  sans redémarrer le serveur.
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
- **Bluetooth** : la section « Bluetooth (sortie audio) » liste les périphériques connus/détectés et permet
  de lancer une recherche, jumeler, connecter/déconnecter ou oublier un appareil, directement depuis
  l'interface web. Se connecter à une enceinte/un casque Bluetooth bascule automatiquement la sortie audio
  du Raspberry Pi vers cet appareil (voir Notes techniques).
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
