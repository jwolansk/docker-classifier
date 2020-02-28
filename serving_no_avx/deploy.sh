#!/bin/sh

docker run -d -p 8501:8501 -v /home/kuba/serving/:/models --mount type=bind,source=/home/kuba/docker-classifier/models.config,target=/models/models.config --name serving_no_avx -t serving_no_avx /usr/bin/tensorflow_model_server --model_config_file=/models/models.config --rest_api_port=8501
