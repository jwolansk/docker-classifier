# docker-classifier
Keras model classifying new images in a folder on docker

Edit dockerfile to provide paths for motionEye volume.

The `serving` and `serving_no_avx` folder contain dockerfiles for `Tensorflow Serving` containers used by the application.

Most CPUs support the AVX instruction set, but if your host runs on a Celeron, or you use a hypervisor that does not provide AVX you'd need the `no_avx` backend.

The `docker_compose.yml` files are meant to be run with Docker Swarm. If the Visualizer is not needed, remove the respective part of the config. Also, edit volume mount paths, to where the model files will be stored on nodes.
