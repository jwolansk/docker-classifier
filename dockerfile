FROM ubuntu:latest

RUN apt-get update \
    && apt-get install -y software-properties-common

RUN apt-get install -y python3-pip python3-dev \
  && cd /usr/local/bin \
  && ln -s /usr/bin/python3 python \
  && pip3 install --upgrade pip

# Install app dependencies, tensorflow 1.5 is compiled with instruction set for my CPU (j3455)
RUN pip3 install --upgrade tensorflow==1.5

RUN pip3 install numpy scipy
RUN pip3 install scikit-learn
RUN pip3 install pillow
RUN pip3 install h5py
RUN pip3 install keras
RUN pip3 install paho-mqtt
RUN pip3 install watchdog

COPY recognize.py /src/recognize.py
COPY run.sh /src/run.sh

CMD "/src/run.sh"