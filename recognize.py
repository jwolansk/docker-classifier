import numpy as np
import logging
import json
import time
from datetime import datetime
from datetime import timedelta
import asyncio
import aiohttp
import janus
from os import listdir
from os.path import isfile, join

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
    folder = "/Users/kuba/motioneye/var/" + CAMERA_NAME + "/"
    classes = ['carpassing', 'delivery', 'dodge', 'opel', 'personpassing', 'truck']
    movement_classes = ['yes', 'no']

    movetimes = []
    classtimes = []

    producerFinished = False
    moveFinished = False
    pathCount = 0

    # load train and test dataset
    async def load_data(self, paths):

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

    async def pathProducer(self, session):
        logger.info("## creating new path producer task")
        await asyncio.sleep(0.5)
        paths = [f for f in listdir(self.folder) if isfile(join(self.folder, f))]

        for path in paths:
            await self.q.async_q.put(self.folder + path)

        logger.info("producer finished with %s paths" % len(paths))
        self.pathCount = len(paths)
        self.producerFinished = True

    async def handleNewPaths(self, session):
        logger.info("## creating new path task")
        while True:

            if self.producerFinished and self.pathCount == 0:
                self.moveFinished = True
                logger.info("move finished")
                return

            path = await self.q.async_q.get()
            logger.debug("#### got q path")
            paths = [path]

            data = await self.load_data(paths)
            if data is None:
                logger.debug("#### none data: " + path)
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
                    self.movetimes.append(time.time() - start_time)
                    logger.debug("####### predictions")
                    logger.debug(predictions)
                    for index, movement_predictions in enumerate(predictions):
                        movement_result = np.argmax(movement_predictions)
                        logString = paths[index] + " %.2f" % (time.time() - start_time) + "s " + self.movement_classes[
                            movement_result] + ' (' + "%.2f" % movement_predictions[movement_result] + ")"

                        if movement_predictions[movement_result] > 0.75:
                            if self.movement_classes[movement_result] == 'yes':
                                element = (paths[index], logString, data[index])
                                await self.highQ.async_q.put(element)

                                continue
                        logger.info(logString)

            except Exception as inst:
                logger.error(type(inst))  # the exception instance
                logger.error(inst.args)  # arguments stored in .args
                logger.error(inst)
            self.pathCount -= 1
            logger.info("%s paths left" % self.pathCount)
            if self.pathCount <= 1:
                self.moveFinished = True
                logger.info("move finished")
                return


    async def handleMovementPaths(self, session):
        logger.info("## creating new move class task")
        while True:
            elements = []
            path = await self.highQ.async_q.get()
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

                    self.classtimes.append(time.time() - start_time)
                    logger.debug("####### predictions")
                    logger.debug(predictions)
                    for index, movement_predictions in enumerate(predictions):
                        result = np.argmax(movement_predictions)
                        logString = elements[index][1] + " - %.2fs ---" % (time.time() - start_time) + " " + self.classes[
                            result] + ' (' + "%.2f" % predictions[index][result] + ")"
                        logger.info(logString)

            except Exception as inst:
                logger.error(type(inst))  # the exception instance
                logger.error(inst.args)  # arguments stored in .args
                logger.error(inst)

            if self.moveFinished and self.highQ.sync_q.empty():
                logger.info("high finished")
                return


    async def run(self, path):

        start_time = time.time()

        self.q = janus.Queue()
        self.highQ = janus.Queue()

        logger.info("--- started")

        async with aiohttp.ClientSession() as session:
            self.tasks = [asyncio.create_task(self.handleNewPaths(session)) for _ in range(1)] +\
                         [asyncio.create_task(self.pathProducer(session))]

            await asyncio.gather(*self.tasks)

            self.tasks = [asyncio.create_task(self.handleMovementPaths(session)) for _ in range(1)]
            await asyncio.gather(*self.tasks)

            avg = 0.0
            for secs in self.movetimes:
                avg += secs
            avg = avg / len(self.movetimes)
            logger.info("move avg: %.2fs" % (avg))

            avg = 0.0
            for secs in self.classtimes:
                avg += secs
            avg = avg / len(self.classtimes)
            logger.info("class avg: %.2fs" % (avg))

            logger.info("avg total time: %.2fs" % ((time.time() - start_time) / len(self.movetimes)))

async def main():

    w = Watcher()
    await w.run("/data/" + CAMERA_NAME + "/")


asyncio.run(main(), debug=False)

