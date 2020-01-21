# docker-classifier
Keras model classifying new images in a folder on docker

Edit dockerfile to provide paths for motionEye volume and a directory with a model.h5

The dockerfile references a Tensorflow wheel compiled without AVX support as it is needed for my CPU (Celeron). If your CPU supports it, commend the entry from the dockerfile and uncomment the following line.
