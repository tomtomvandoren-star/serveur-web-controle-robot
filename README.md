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
- L'interface est responsive et utilisable aussi bien sur ordinateur que sur téléphone.

## Notes techniques

- Le flux caméra utilise OpenCV (`cv2.VideoCapture`) avec le backend V4L2 pour lire `/dev/video0`.
- Le serveur écoute sur toutes les interfaces (`0.0.0.0:5000`) pour être accessible depuis d'autres appareils.
- À l'arrêt du serveur (Ctrl+C), les moteurs sont coupés, le GPIO est proprement libéré et la caméra est
  relâchée.
