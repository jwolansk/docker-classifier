#!/usr/bin/env bash
docker run -d --name objectrecognition -v /home/kuba/motioneye/var:/data/ -v /home/kuba/newhome/objectrecognition/objectrecognition:/model/ objectrecognition:latest
