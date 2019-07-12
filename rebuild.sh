#!/bin/sh
git pull

docker stop objectrecognition
docker rm objectrecognition
docker build -t objectrecognition .

docker run -it --name objectrecognition -v /home/kuba/motioneye/var:/data/ -v /home/kuba/newhome/objectrecognition/objectrecognition:/model/ objectrecognition:latest
