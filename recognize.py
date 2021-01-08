import numpy as np
import subprocess
import paho.mqtt.client as mqtt
import logging
import json
from datetime import datetime
from datetime import timedelta
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import asyncio
import aiohttp
import janus
import socket
import time
import tensorflow as tf

import os.path

from PIL import ImageFile
from PIL import Image

ImageFile.LOAD_TRUNCATED_IMAGES = True

hostname = "192.168.1.200"
CAMERA_NAME = "gate"
BATCHSIZE = 1

logging.basicConfig(level=logging.INFO)
handle = "obj-reco"
logger = logging.getLogger(handle)

ori_image_width = 53
ori_image_height = 40

image_width = 53
image_height = 27
channels = 3

folder = "/data/" + CAMERA_NAME + "/"

class Watcher():
    img = Image.new('RGB', (1, 1))

    classes = ['carpassing', 'delivery', 'dodge', 'opel', 'personpassing', 'truck']
    movement_classes = ['yes', 'no']
    client = mqtt.Client("docker-classifier-2.0")

    pathsChecked = {}


    def __init__(self):
        self.observer = Observer()

    def load_models(self):
        path = "/model/"
        self.moveInterpreter = tf.lite.Interpreter(model_path=path + "movement.tflite")
        self.moveInterpreter.allocate_tensors()
        self.objectsInterpreter = tf.lite.Interpreter(model_path=path + "objects.tflite")
        self.objectsInterpreter.allocate_tensors()

    # load train and test dataset
    async def load_data(self, paths):

        imagedata = np.ndarray(shape=(len(paths), image_height, image_width, channels),
                               dtype=np.float32)
        for index,filename in enumerate(paths):

            try:
                img = Image.open(filename)  # this is a PIL image
            except:
                return None

            img = img.resize((ori_image_width, ori_image_height))
            img = img.crop((0, ori_image_height - image_height, ori_image_width, ori_image_height))

            # Convert to Numpy Array
            x = np.array(img)
            x = x.reshape((image_height, image_width, 3))
            # Normalize
            x = x / 256.0
            # x = np.subtract(x, self.background_avg)
            imagedata[index] = x

        return imagedata

    async def handleFailedPaths(self, session):
        logger.info("## creating new failed path task")
        while True:

            logger.debug("## failed path task sleep")
            await asyncio.sleep(0.1)

            path = await self.failedQ.get()
            logger.debug("#### got failed q path")

            await asyncio.sleep(0.1)
            if os.path.exists(path):
                logger.debug("path exists: " + path)
                await self.q.async_q.put(path)
            else:
                logger.debug("path does not exist anymore: " + path)


    async def handleNewPaths(self, session):
        logger.info("## creating new path task")
        while True:

            logger.debug("## path task sleep")
            await asyncio.sleep(0.1)

            path = await self.q.async_q.get()
            logger.debug("#### got q path")
            paths = [path]
            if path in self.pathsChecked:
                continue
            data = await self.load_data(paths)
            if data is None:
                logger.debug("#### none data: " + path)
                await self.failedQ.put(path)
                await asyncio.sleep(0.1)
                continue
            if data[0] is None:
                logger.debug("#### none first data")
                await self.failedQ.put(path)
                await asyncio.sleep(0.1)
                continue

            self.pathsChecked[path] = datetime.now()

            logger.debug("## checking " + str(1) + " paths")

            start_time = time.time()

            input_details = self.moveInterpreter.get_input_details()
            output_details = self.moveInterpreter.get_output_details()
            self.moveInterpreter.set_tensor(input_details[0]['index'], data)

            self.moveInterpreter.invoke()
            movement_predictions = list(self.moveInterpreter.get_tensor(output_details[0]['index'])[0])

            logger.debug("####### predictions")
            logger.debug(movement_predictions)
            index = 0
            movement_result = np.argmax(movement_predictions)
            logString = paths[0] + " %.3f" % (time.time() - start_time) + "s " + self.movement_classes[
                movement_result] + ' (' + "%.2f" % movement_predictions[movement_result] + ")"

            if movement_predictions[movement_result] > 0.75:
                if self.movement_classes[movement_result] == 'yes':
                    element = (paths[index], logString, data[index])
                    await self.highQ.put(element)

                    subprocess.call("cp '" + paths[index] + "' /data/gate/lastmove.jpg", shell=True)
                    self.client.publish("gate/object", self.movement_classes[movement_result])
                    continue
            yesnopath = "/data/" + CAMERA_NAME + "/" + self.movement_classes[movement_result]
            if not os.path.exists(yesnopath):
                subprocess.call('mkdir ' + yesnopath + " &> /dev/null", shell=True)

            logger.info(logString)
            await asyncio.sleep(0.5)
            subprocess.call("mv '" + paths[index] + "' " + yesnopath, shell=True)


    async def handleMovementPaths(self, session):
        logger.info("## creating new move class task")
        while True:
            elements = []
            path = await self.highQ.get()
            elements.append(path)
            logger.debug("#### got highq path")

            logger.debug("## checking move " + str(len(elements)) + " paths")
            data = np.ndarray(shape=(len(elements), image_height, image_width, channels),
                              dtype=np.float32)
            for index, image in enumerate(elements):
                data[index] = image[2]

            start_time = time.time()

            input_details = self.objectsInterpreter.get_input_details()
            output_details = self.objectsInterpreter.get_output_details()
            self.objectsInterpreter.set_tensor(input_details[0]['index'], data)

            self.objectsInterpreter.invoke()
            movement_predictions = list(self.objectsInterpreter.get_tensor(output_details[0]['index'])[0])

            logger.debug("####### predictions")
            logger.debug(movement_predictions)
            index = 0
            result = np.argmax(movement_predictions)
            logString = elements[index][1] + " - %.3fs ---" % (time.time() - start_time) + " " + self.classes[
                result] + ' (' + "%.2f" % movement_predictions[result] + ")"
            logger.info(logString)
            if movement_predictions[result] > 0.55:
                self.client.publish("gate/object", self.classes[result])
            classpath = "/data/" + CAMERA_NAME + "/" + self.classes[result]
            if not os.path.exists(classpath):
                subprocess.call("mkdir " + classpath + " &> /dev/null", shell=True)
            subprocess.call("mv '" + elements[index][0] + "' " + classpath, shell=True)


    async def pathCleaner(self):
        while True:
            await asyncio.sleep(10)
            newPaths = {}
            for path, timestamp in self.pathsChecked.items():
                logger.debug("checking: " + path)
                if timestamp + timedelta(seconds=20) < datetime.now():
                    newPaths[path] = timestamp
                else:
                    logger.debug("cleaned: " + path)

            self.pathsChecked = newPaths

    async def run(self, path):

        self.q = janus.Queue()
        self.highQ = asyncio.Queue()
        self.failedQ = asyncio.Queue()

        self.load_models()

        event_handler = Handler(q=self.q.sync_q, ignore_patterns=['/data/detected.jpg', '/data/' + CAMERA_NAME + '/lastmove.jpg', '*.DS_Store', '*.mp4'])

        logger.info("--- started")

        self.observer.schedule(event_handler, path, recursive=True)
        self.observer.start()
        logger.info("handler started")

        self.client.connect("192.168.1.253", 1883, 60)
        self.client.loop_start()

        def on_disconnect(client, userdata, rc):
            if rc != 0:
                logger.info("Unexpected MQTT disconnection. Will auto-reconnect")

        def on_connect(client, userdata, rc, other):
            logger.info("MQTT Client Connected")

        self.client.on_disconnect = on_disconnect
        self.client.on_connect = on_connect

        async with aiohttp.ClientSession() as session:
            self.tasks = [asyncio.create_task(self.handleNewPaths(session)) for _ in range(10)] +\
                         [asyncio.create_task(self.handleMovementPaths(session)) for _ in range(6)] +\
                         [asyncio.create_task(self.handleFailedPaths(session))] +\
                         [asyncio.create_task(self.pathCleaner())]

            await asyncio.gather(*self.tasks)


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
        logger.debug(event)
        path = "%s" % event.src_path
        self.q.put(path)


async def main():

    w = Watcher()
    await w.run(folder)


asyncio.run(main(), debug=False)

