import numpy as np
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from PIL import Image
import subprocess
import paho.mqtt.client as mqtt
import gc

import logging
import json
import requests
import time
import queue
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

import os.path

from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

hostname = "192.168.1.200"
CAMERA_NAME = "gate"

logging.basicConfig(level=logging.INFO)
handle = "obj-reco"
logger = logging.getLogger(handle)

image_width = 53
image_height = 40

channels = 3

class Watcher():
    img = Image.new('RGB', (1, 1))
    def __init__(self):
        self.observer = Observer()

    def run(self, path):
        q = queue.LifoQueue(10)
        highQ = queue.LifoQueue(10)
        event_handler = Handler(q=q, ignore_patterns=['/data/detected.jpg', '/data/' + CAMERA_NAME + '/lastmove.jpg', '*.DS_Store', '*.mp4'])

        logger.info("--- started")
        # load train and test dataset
        def load_data(paths):

            imagedata = np.ndarray(shape=(len(paths), image_height, image_width, channels),
                                   dtype=np.float32)
            for index,filename in enumerate(paths):

                try:
                    img = load_img(filename)  # this is a PIL image
                except:
                    return None
                # img = img.resize((640, 480))
                ratio = img.size[0] / img.size[1]
                img = img.resize((int(ratio * image_height), image_height))
                left = int((ratio * image_height - image_width) / 2)
                top = 0
                right = left + image_width
                bottom = image_height

                img = img.crop((left, top, right, bottom))

                # Convert to Numpy Array
                x = img_to_array(img)
                x = x.reshape((image_height, image_width, 3))
                # Normalize
                x = x / 256.0
                imagedata[index] = x

            return imagedata

        # load model
        folder = "/data/" + CAMERA_NAME + "/"

        classes = ['carpassing', 'delivery', 'dodge', 'opel', 'personpassing', 'truck']
        movement_classes = ['yes', 'no']

        self.observer.schedule(event_handler, path, recursive=True)
        self.observer.start()
        logger.info("handler started")

        client = mqtt.Client("docker-classifier-2.0-mbp")
        client.connect("192.168.1.253", 1883, 60)
        client.loop_start()

        def on_disconnect(client, userdata, rc):
            if rc != 0:
                logger.info("Unexpected MQTT disconnection. Will auto-reconnect")

        def on_connect(client, userdata, rc):
            logger.info("MQTT Client Connected")

        client.on_disconnect = on_disconnect
        client.on_connect = on_connect

        try:
            client.loop_start()

            while True:
                if not q.empty():
                    time.sleep(0.1)
                    pathSet = set([])
                    while not q.empty():
                        path = q.get(False)
                        pathSet.add(path)

                    paths = list(pathSet)
                    data = load_data(paths)
                    if data is None:
                        continue
                    if not data[0] is None:
                        logger.debug(data[0])
                    else:
                        continue

                    try:
                        start_time = time.time()
                        servingData = json.dumps(
                            {"signature_name": "serving_default", "instances": data.tolist()})
                        headers = {"content-type": "application/json"}
                        json_response = requests.post('http://' + hostname + ':8501/v1/models/movement:predict',
                                                      data=servingData, headers=headers)
                        predictions = json.loads(json_response.text)['predictions']

                        logger.debug("####### predictions")
                        logger.debug(predictions)
                        for index, movement_predictions in enumerate(predictions):
                            movement_result = np.argmax(movement_predictions)
                            logString = paths[index] + " %.2f" % (time.time() - start_time) + "s " + movement_classes[
                                movement_result] + ' (' + "%.2f" % movement_predictions[movement_result] + ")"

                            if movement_predictions[movement_result] > 0.75:
                                if movement_classes[movement_result] == 'yes':
                                    element = (paths[index], logString, data[index])
                                    highQ.put(element)

                                    subprocess.call("cp '" + paths[index] + "' /data/gate/lastmove.jpg", shell=True)
                                    client.publish("gate/object", movement_classes[movement_result])
                                    continue
                            yesnopath = "/data/" + CAMERA_NAME + "/" + movement_classes[movement_result]
                            if not os.path.exists(yesnopath):
                                subprocess.call('mkdir ' + yesnopath + " &> /dev/null", shell=True)

                            logger.info(logString)
                            subprocess.call("mv '" + paths[index] + "' " + yesnopath, shell=True)

                    except Exception as inst:
                        logger.error(type(inst))  # the exception instance
                        logger.error(inst.args)  # arguments stored in .args
                        logger.error(inst)

                if not highQ.empty():
                    elements = []
                    while not highQ.empty():
                        element = highQ.get(False)
                        elements.append(element)

                    logger.debug(elements)
                    data = np.ndarray(shape=(len(elements), image_height, image_width, channels),
                                           dtype=np.float32)
                    for index, image in enumerate(elements):
                        data[index] = image[2]

                    try:
                        start_time = time.time()
                        servingData = json.dumps(
                            {"signature_name": "serving_default", "instances": data.tolist()})
                        headers = {"content-type": "application/json"}
                        json_response = requests.post('http://' + hostname + ':8501/v1/models/objects:predict',
                                                      data=servingData, headers=headers)
                        predictions = json.loads(json_response.text)['predictions']

                        logger.debug("####### predictions")
                        logger.debug(predictions)
                        for index, movement_predictions in enumerate(predictions):
                            result = np.argmax(movement_predictions)
                            logString = elements[index][1] + " - %.2fs ---" % (time.time() - start_time) + " " + classes[
                                result] + ' (' + "%.2f" % predictions[index][result] + ")"
                            logger.info(logString)
                            if predictions[index][result] > 0.45:
                                client.publish("gate/object", classes[result])
                            classpath = "/data/" + CAMERA_NAME + "/" + classes[result]
                            if not os.path.exists(classpath):
                                subprocess.call("mkdir " + classpath + " &> /dev/null", shell=True)
                            subprocess.call("mv '" + elements[index][0] + "' " + classpath, shell=True)

                    except Exception as inst:
                        logger.error(type(inst))  # the exception instance
                        logger.error(inst.args)  # arguments stored in .args
                        logger.error(inst)

        except KeyboardInterrupt:
            logger.info("stop")
        self.observer.join()


class Handler(PatternMatchingEventHandler):

    def __init__(self, q, ignore_patterns):
        self.q = q
        super(Handler, self).__init__(
            ignore_patterns=ignore_patterns,
            ignore_directories=True
        )

    def on_created(self, event):
        if event.is_directory:
            return None

        # Take any action here when a file is first created.
        path = "%s" % event.src_path
        # print(path)
        self.q.put(path)


if __name__ == '__main__':


    logger.info("gc enabled" if gc.isenabled() else "gc disabled")
    w = Watcher()
    w.run("/data/" + CAMERA_NAME + "/")

