import numpy as np
import subprocess
import paho.mqtt.client as mqtt
import logging
import json
import time
import queue
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
import asyncio
import aiohttp
import requests

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

image_width = 53
image_height = 40
channels = 3


class Watcher():
    img = Image.new('RGB', (1, 1))
    pathQueue = queue.Queue()
    folder = "/data/" + CAMERA_NAME + "/"
    classes = ['carpassing', 'delivery', 'dodge', 'opel', 'personpassing', 'truck']
    movement_classes = ['yes', 'no']
    client = mqtt.Client("docker-classifier-2.0-mbp")


    def __init__(self):
        self.observer = Observer()

    # load train and test dataset
    def load_data(self, paths):

        imagedata = np.ndarray(shape=(len(paths), image_height, image_width, channels),
                               dtype=np.float32)
        for index,filename in enumerate(paths):

            try:
                img = Image.open(filename)  # this is a PIL image
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
            x = np.array(img)
            x = x.reshape((image_height, image_width, 3))
            # Normalize
            x = x / 256.0
            imagedata[index] = x

        return imagedata

    async def handleNewPaths(self, session):
        logger.info("## creating new path task")
        while True:

            logger.debug("## path task sleep")
            path = await self.q.get()
            logger.debug("#### got q path")
            paths = [path]
            data = self.load_data(paths)
            if data is None:
                logger.debug("#### none data")
                continue
            if not data[0] is None:
                logger.debug(data[0])
            else:
                logger.debug("#### none first data")
                continue

            logger.debug("## checking " + str(1) + " paths")
            try:
                start_time = time.time()
                servingData = json.dumps(
                    {"signature_name": "serving_default", "instances": data.tolist()})
                headers = {"content-type": "application/json"}

                url = 'http://' + hostname + ':8501/v1/models/movement:predict'
                async with session.post(url, data=servingData, headers=headers) as response:
                    json_response = await response.json()

                    predictions = json_response['predictions']

                    logger.debug("####### predictions")
                    logger.debug(predictions)
                    for index, movement_predictions in enumerate(predictions):
                        movement_result = np.argmax(movement_predictions)
                        logString = paths[index] + " %.2f" % (time.time() - start_time) + "s " + self.movement_classes[
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
                        subprocess.call("mv '" + paths[index] + "' " + yesnopath, shell=True)

            except Exception as inst:
                logger.error(type(inst))  # the exception instance
                logger.error(inst.args)  # arguments stored in .args
                logger.error(inst)


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

            try:
                start_time = time.time()
                servingData = json.dumps(
                    {"signature_name": "serving_default", "instances": data.tolist()})
                headers = {"content-type": "application/json"}

                url = 'http://' + hostname + ':8501/v1/models/objects:predict'
                async with session.post(url, data=servingData, headers=headers) as response:
                    json_response = await response.json()

                    predictions = json_response['predictions']

                    logger.debug("####### predictions")
                    logger.debug(predictions)
                    for index, movement_predictions in enumerate(predictions):
                        result = np.argmax(movement_predictions)
                        logString = elements[index][1] + " - %.2fs ---" % (time.time() - start_time) + " " + self.classes[
                            result] + ' (' + "%.2f" % predictions[index][result] + ")"
                        logger.info(logString)
                        # if predictions[index][result] > 0.45:
                            # self.client.publish("gate/object", self.classes[result])
                        classpath = "/data/" + CAMERA_NAME + "/" + self.classes[result]
                        if not os.path.exists(classpath):
                            subprocess.call("mkdir " + classpath + " &> /dev/null", shell=True)
                        subprocess.call("mv '" + elements[index][0] + "' " + classpath, shell=True)

            except Exception as inst:
                logger.error(type(inst))  # the exception instance
                logger.error(inst.args)  # arguments stored in .args
                logger.error(inst)
            # await asyncio.sleep(0.1)



    async def producePaths(self):
        logger.info("## creating new path producer task")
        try:
            self.client.loop_start()

            while True:

                logger.debug("sleeping")
                path = self.pathQueue.get()
                logger.debug(path)
                await self.q.put(path)
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            logger.info("stop")
        self.observer.join()

    async def run(self, path):

        self.q = asyncio.Queue()
        self.highQ = asyncio.Queue()

        event_handler = Handler(q=self.pathQueue, ignore_patterns=['/data/detected.jpg', '/data/' + CAMERA_NAME + '/lastmove.jpg', '*.DS_Store', '*.mp4'])

        logger.info("--- started")

        self.observer.schedule(event_handler, path, recursive=True)
        self.observer.start()
        logger.info("handler started")

        self.client.connect("192.168.1.253", 1883, 60)
        self.client.loop_start()

        def on_disconnect(client, userdata, rc):
            if rc != 0:
                logger.info("Unexpected MQTT disconnection. Will auto-reconnect")

        def on_connect(client, userdata, rc):
            logger.info("MQTT Client Connected")

        self.client.on_disconnect = on_disconnect
        self.client.on_connect = on_connect

        async with aiohttp.ClientSession() as session:
            self.tasks = [asyncio.create_task(self.handleNewPaths(session)) for _ in range(5)] +\
                         [asyncio.create_task(self.handleMovementPaths(session)) for _ in range(4)] +\
                         [asyncio.create_task(self.producePaths())]

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
        path = "%s" % event.src_path
        self.q.put(path)


async def main():

    w = Watcher()
    await w.run("/data/" + CAMERA_NAME + "/")


asyncio.run(main())

