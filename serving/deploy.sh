#!/bin/sh

docker run -d -p 8501:8501 -v /Users/kuba/serving/:/models --mount type=bind,source=/Users/kuba/Documents/home/docker-classifier/models.config,target=/models/models.config --name serving -t serving /usr/bin/tensorflow_model_server --model_config_file=/models/models.config --rest_api_port=8501
