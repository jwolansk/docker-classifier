FROM ubuntu:latest

RUN apt-get update \
    && apt-get install -y software-properties-common python-pip

# Install app dependencies, tensorflow 1.5 is compiled with instruction set for my CPU (j3455)
RUN pip install --upgrade tensorflow==1.5

RUN pip install numpy scipy
RUN pip install scikit-learn
RUN pip install pillow
RUN pip install h5py
RUN pip install keras
RUN pip install paho-mqtt
RUN pip install watchdog

COPY recognize.py /src/recognize.py
COPY run.sh /src/run.sh

CMD "/src/run.sh"