#FROM ubuntu:bionic
FROM python:3.7-buster

RUN pip3 install --upgrade pip

# comment the following 4 lines if you have AVX support
# download the following file from the internet
#COPY tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl /src/tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl
#RUN /usr/bin/python --version
#RUN pip3 install --verbose /src/tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl
#RUN rm /src/tensorflow-2.0.0-cp37-cp37m-linux_x86_64.whl

# uncomment the following line if you have AVX support
RUN pip3 install tensorflow

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
