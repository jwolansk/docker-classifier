FROM ubuntu:latest

RUN apt-get update \
    && apt-get install -y software-properties-common libssl-dev openssl python3.8

RUN rm /usr/bin/python3
RUN ln -s /usr/bin/python3.8 /usr/bin/python
RUN ln -s /usr/bin/python3.8 /usr/bin/python3

RUN apt-get install -y python3-pip #python3-dev 
RUN pip3 install --upgrade pip

# comment the following 4 lines if you have AVX support
RUN pip3 install --verbose https://github.com/inoryy/tensorflow-optimized-wheels/releases/download/v2.1.0/tensorflow-2.1.0-cp37-cp37m-linux_x86_64.whl

# uncomment the following line if you have AVX support
#RUN pip3 install tensorflow==2.0

RUN pip3 install numpy scipy
RUN pip3 install scikit-learn
RUN pip3 install pillow
RUN pip3 install h5py
RUN pip3 install paho-mqtt
RUN pip3 install watchdog
RUN pip3 install requests
RUN pip3 install aiohttp
RUN pip3 install aiojobs
RUN pip3 install janus

CMD "/model/run.sh"
