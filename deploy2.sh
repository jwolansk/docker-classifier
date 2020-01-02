#!/usr/bin/env bash
docker run -d --name objectrecognition2 -v /home/kuba/motioneye/var:/data/ -v /home/kuba/docker-classifier:/model/ objectrecognition2:latest
