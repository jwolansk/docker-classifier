FROM ubuntu:latest

RUN apt-get update \
    && apt-get install -y software-properties-common libssl-dev openssl python3.7

RUN rm /usr/bin/python3
RUN ln -s /usr/bin/python3.7 /usr/bin/python
RUN ln -s /usr/bin/python3.7 /usr/bin/python3

RUN apt-get install -y python3-pip #python3-dev 
RUN pip3 install --upgrade pip

# comment the following 4 lines if you have AVX support
#COPY tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl /src/tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl
#RUN /usr/bin/python --version
#RUN pip3 install --verbose /src/tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl
#RUN rm /src/tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl

# uncomment the following line if you have AVX support
RUN pip3 install tensorflow==2.0

RUN pip3 install numpy scipy
RUN pip3 install scikit-learn
RUN pip3 install pillow
RUN pip3 install h5py
RUN pip3 install paho-mqtt
RUN pip3 install watchdog

CMD "/model/run.sh"
