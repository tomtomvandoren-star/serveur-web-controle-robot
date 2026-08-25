# Contrôle du moteur via interface web

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
- Le bouton « MAINTENIR POUR ACTIVER » fonctionne comme dans ton script Tkinter original :
  appui = moteur ON, relâchement = moteur OFF. Ça marche aussi bien à la souris qu'au doigt sur un écran tactile.
- Le GPIO 17 est piloté exactement comme avant.

## Notes techniques

- Le flux caméra utilise OpenCV (`cv2.VideoCapture`) avec le backend V4L2 pour lire `/dev/video0`.
- Le serveur écoute sur toutes les interfaces (`0.0.0.0:5000`) pour être accessible depuis d'autres appareils.
- À l'arrêt du serveur (Ctrl+C), le GPIO est proprement remis à zéro et libéré, et la caméra est relâchée.
