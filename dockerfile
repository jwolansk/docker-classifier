FROM ubuntu:latest

RUN apt-get update \
    && apt-get install -y software-properties-common libssl-dev openssl python3.7

RUN rm /usr/bin/python3
RUN ln -s /usr/bin/python3.7 /usr/bin/python
RUN ln -s /usr/bin/python3.7 /usr/bin/python3

RUN apt-get install -y python3-pip #python3-dev 
RUN pip3 install --upgrade pip

RUN pip3 install numpy scipy
RUN pip3 install scikit-learn
RUN pip3 install pillow
RUN pip3 install h5py
RUN pip3 install paho-mqtt
RUN pip3 install watchdog
RUN pip3 install requests

CMD "/model/run.sh"
