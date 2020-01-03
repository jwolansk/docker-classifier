import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from PIL import Image
import subprocess
from subprocess import call
from datetime import datetime
import paho.mqtt.client as mqtt
import sys

import time
import queue
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler

from PIL import ImageFile
ImageFile.LOAD_TRUNCATED_IMAGES = True

CAMERA_NAME = "gate"
class Watcher():

    def __init__(self):
        self.observer = Observer()

    def run(self, path):
        q = queue.LifoQueue(10)
        event_handler = Handler(q=q, ignore_patterns=['/data/detected.jpg', '/data/' + CAMERA_NAME + '/lastmove.jpg', '*.DS_Store', '*.mp4'])

        # load train and test dataset
        def load_data(file):

            image_width = 53
            image_height = 40

            channels = 3
            nb_classes = 11

            imagedata = np.ndarray(shape=(1, image_height, image_width, channels),
                                   dtype=np.float32)
            try:
                img = load_img(file)  # this is a PIL image
            except Exception as e:
                print(e)
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
            imagedata[0] = x

            return imagedata

        # load model
        folder = "/data/" + CAMERA_NAME + "/"

        movement = load_model('/model/model.h5')
        objects = load_model('model/model_objects.h5')
        # summarize model.
        objects.summary()

        classes = ['carpassing', 'delivery', 'dodge', 'opel', 'personpassing', 'truck']
        movement_classes = ['yes', 'no']

        print("movement model loaded")
        self.observer.schedule(event_handler, path, recursive=True)
        self.observer.start()
        print("handler started")
        try:
            while True:
                if not q.empty():
                    path = q.get()

                    data = load_data(path)
                    if data is None:
                        continue

                    start_time = time.time()
                    # result = model.predict_classes(data)[0]
                    probs = movement.predict(data)
                    print("--- movement prediction: %s ---" % (time.time() - start_time))

                    movement_result = probs.argmax(axis=-1)[0]

                    print(path + ' ' + movement_classes[movement_result])
                    print(probs)

                    if probs[0][movement_result] > 0.75:
                        if movement_classes[movement_result] == 'yes':

                            subprocess.call("cp '" + path.replace("/gate/", "/gatehigh/") + "' /data/gate/lastmove.jpg || cp '" + path + "' /data/gate/lastmove.jpg", shell=True)
                            #subprocess.call("cp '" + path + "' /data/" + CAMERA_NAME + "/lastmove.jpg", shell=True)

                            client = mqtt.Client()
                            client.connect("192.168.1.253", 1883, 60)
                            client.publish("gate/object", movement_classes[movement_result])

                            probs = objects.predict(data)
                            print("--- objects prediction: %s ---" % (time.time() - start_time))

                            result = probs.argmax(axis=-1)[0]

                            print(path + ' ' + classes[result])
                            print(probs[0][result])
                            if probs[0][result] > 0.70:
                                client.publish("gate/object", classes[result])

                            subprocess.call("mkdir /data/" + CAMERA_NAME + "/" + classes[result] + "&> /dev/null", shell=True)
                            subprocess.call("mv '" + path + "' /data/" + CAMERA_NAME + "/" + classes[result], shell=True)
                    subprocess.call("mkdir /data/" + CAMERA_NAME + "/" + movement_classes[movement_result] + "&> /dev/null", shell=True)
                    subprocess.call("mv '" + path + "' /data/" + CAMERA_NAME + "/" + movement_classes[movement_result], shell=True)
                else:

                    time.sleep(0.5)
        except KeyboardInterrupt:
            print("stop")
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

    w = Watcher()
    w.run("/data/" + CAMERA_NAME + "/")

