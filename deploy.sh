#!/usr/bin/env bash
docker run -d --name objectrecognition2 -v /Users/kuba/motioneye/var:/data/ -v /Users/kuba/Documents/home/docker-classifier:/model/ objectrecognition2:latest
