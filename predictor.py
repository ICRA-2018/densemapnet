'''DenseMapNet - a tiny network for fast disparity estimation
from stereo images

Predictor class manages the data, training and prediction

Atienza, R. "Fast Disparity Estimation using Dense Networks".
International Conference on Robotics and Automation,
Brisbane, Australia, 2018.
'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import keras
from keras.callbacks import ModelCheckpoint, LambdaCallback

import numpy as np

import argparse
import os
from os import path
import matplotlib.image as img
import matplotlib.pyplot as plt
from scipy import misc
import gc

from utils import Settings
from utils import ElapsedTimer
from densemapnet import DenseMapNet


class Predictor(object):
    def __init__(self, settings=Settings()):
        self.settings = settings
        self.pdir = "dataset" 
        self.get_max_disparity()
        self.load_test_data()
        self.model = None

    def get_max_disparity(self):
        self.dmax = 0
        self.dmin = 255
        count = self.settings.num_dataset + 1
        for i in range(1, count, 1):
            filename = self.settings.dataset + ".train.disparity.%d.npz" % i
            print("Loading... ", filename)
            self.train_dx = np.load(os.path.join(self.pdir, filename))['arr_0']
            self.dmax =  max(self.dmax, np.amax(self.train_dx))
            self.dmin =  min(self.dmin, np.amin(self.train_dx))
        filename = self.settings.dataset + ".test.disparity.npz"
        print("Loading... ", filename)
        self.test_dx = np.load(os.path.join(self.pdir, filename))['arr_0']
        self.dmax =  max(self.dmax, np.amax(self.test_dx))
        self.dmin =  min(self.dmin, np.amin(self.test_dx))
        print("Max disparity: ", self.dmax)
        print("Min disparity: ", self.dmin)
        self.test_dx = self.test_dx.astype('float32')
        self.test_dx = np.reshape(self.test_dx, [-1, self.test_dx.shape[1],self.test_dx.shape[2],1])
        self.test_dx = self.test_dx / self.dmax

    def load_test_data(self):
        filename = self.settings.dataset + ".test.left.npz"
        print("Loading... ", filename)
        self.test_lx = np.load(os.path.join(self.pdir, filename))['arr_0']
        filename = self.settings.dataset + ".test.right.npz"
        print("Loading... ", filename)
        self.test_rx = np.load(os.path.join(self.pdir, filename))['arr_0']

    def load_train_data(self, index):
        self.train_lx = None
        self.train_rx = None
        self.train_dx = None
        gc.collect()

        filename = self.settings.dataset + ".train.left.%d.npz" % index
        print("Loading... ", filename)
        self.train_lx = np.load(os.path.join(self.pdir, filename))['arr_0']

        filename = self.settings.dataset + ".train.right.%d.npz" % index
        print("Loading... ", filename)
        self.train_rx = np.load(os.path.join(self.pdir, filename))['arr_0']

        filename = self.settings.dataset + ".train.disparity.%d.npz" % index
        print("Loading... ", filename)
        self.train_dx = np.load(os.path.join(self.pdir, filename))['arr_0']

        self.train_dx = self.train_dx.astype('float32')
        self.train_dx = np.reshape(self.train_dx, [-1, self.train_dx.shape[1],self.train_dx.shape[2],1])
        self.train_dx = self.train_dx / self.dmax

        self.xdim = self.settings.xdim = self.train_lx.shape[2]
        self.ydim = self.settings.ydim = self.train_lx.shape[1]
        self.channels = self.settings.channels = self.train_lx.shape[3]

    def train_network(self):
        # train in batch of decreasing number of epochs (8, 4, 2, 1)
        for i in range(3, -1, -1):
            epochs = 2 ** i
            self.train_batch(epochs=epochs)
            self.predict_disparity()

    def train_batch(self, epochs=10):
        count = self.settings.num_dataset + 1
        checkdir = "checkpoint"
        os.mkdir(checkdir)
        for i in range(1, count, 1):
            # self.s1 = 0
            # self.t1 = 0
            # self.s2 = 0
            # self.t2 = 0
            # self.j = i
            filepath = os.path.join(checkdir, "densemapnet_weights.{epoch:02d}.h5")
            checkpoint = ModelCheckpoint(filepath=filepath, save_weights_only=True, verbose=1, save_best_only=False)
            # predict_callback = LambdaCallback(on_epoch_end=lambda epoch, logs: self.predict_disparity())
            # callbacks = [checkpoint, predict_callback]
            callbacks = [checkpoint]
            self.load_train_data(i)
            x = [self.train_lx, self.train_rx]
            if self.model is None:
                self.network = DenseMapNet(settings=self.settings)
                self.model = self.network.build_model()

            self.model.fit(x, self.train_dx, epochs=epochs, batch_size=4, shuffle=True, callbacks=callbacks)
        
            # ave = self.s1/self.t1
            # log = "set total, %d, iter, %d, train size, %d, train epe, %f" % (self.j, self.i, self.t1, ave*self.max)
            # print("Total Train EPE: %f %fpix" % (ave, ave*self.max))
            # ave = self.s2/self.t2
            # print("Total Test EPE: %f %fpix" % (ave, ave*self.max))
            # log += ", test size, %d, test epe, %f\n" % (self.t2, ave*self.max)
            # fd = open("flying.epe.txt", "a")
            # fd.write(log)
            # fd.close()

    def mkdirs(self, pdir):
        filepath = os.path.join(pdir, "train_left")
        os.makedirs(os.path.dirname(filepath))
        filepath = os.path.join(pdir, "train_right")
        os.makedirs(os.path.dirname(filepath))
        filepath = os.path.join(pdir, "train_ground")
        os.makedirs(os.path.dirname(filepath))
        filepath = os.path.join(pdir, "test_left")
        os.makedirs(os.path.dirname(filepath))
        filepath = os.path.join(pdir, "test_right")
        os.makedirs(os.path.dirname(filepath))
        filepath = os.path.join(pdir, "test_ground")
        os.makedirs(os.path.dirname(filepath))

    def get_epe(self, use_train_data=True):
        if use_train_data:
            lx = self.train_lx
            rx = self.train_rx
            dx = self.train_dx
            print("Using train data...")
        else:
            lx = self.test_lx
            rx = self.test_rx
            dx = self.test_dx
            print("Using test data...")

        # sum of all errors (normalized)
        s = 0
        # count of images
        t = 0
        nsamples = lx.shape[0]
        for i in range(0, nsamples, 1):
            indexes = np.arange(i, i + 1)
            left_images = lx[indexes, :, :, : ]
            right_images = rx[indexes, :, :, : ]
            disparity_images = dx[indexes, :, :, : ]
            # measure the speed of prediction on the 10th sample to avoid variance
            if i == 10:
                timer = ElapsedTimer()
                predicted_disparity = self.model.predict([left_images, right_images])
                timer.elapsed_time()
            else:
                predicted_disparity = self.model.predict([left_images, right_images])

            a = predicted_disparity[0, :, :, :]
            b = disparity_images[0, :, :, :]
            ab = a - b
            dim = a.shape[0] * a.shape[1]
            # normalized error on all pixels
            e = np.sum(np.absolute(ab))
            e = e.astype('float32')
            e = e / dim
            s += e
            t += 1

        epe = s / t 
        # epe in pix units
        pix_epe = epe * self.dmax
        print("EPE: %f %fpix" % (epe, pix_epe))


    def predict_disparity(self):

        self.get_epe()
        self.get_epe(use_train_data=False)

        return

        pdir = "disparity"
        self.mkdirs(pdir)

        s = 0
        t = 0
        nsamples = self.train_lx.shape[0]

        for i in range(0, nsamples, 1):
            indexes = np.arange(i, i + 1)
            left_images = self.train_lx[ indexes, :, :, : ]
            right_images = self.train_rx[ indexes, :, :, : ]
            disparity_images = self.train_dx[ indexes, :, :, : ]
            if i == 10:
                timer = ElapsedTimer()
                predicted_disparity = self.model.predict([left_images, right_images])
                timer.elapsed_time()
            else:
                predicted_disparity = self.model.predict([left_images, right_images])

            a = predicted_disparity[0, :, :, :]
            b = disparity_images[0, :, :, :]
            ab = a - b
            dim = a.shape[0] * a.shape[1]
            e = np.sum(np.absolute(ab))
            e = e.astype('float32')
            e = e / dim
            s += e
            t += 1

            continue 

            filename = parent + "%04d.png" % indexes[i]
            image = predicted_disparity[i, :, :, :]
            image *= (self.max/self.dmax)
            size = [image.shape[0],image.shape[1]]
            image =  np.clip(image, 0.0, 1.0)
            image *= 255
            image = image.astype(np.uint8)
            image = np.reshape(image, size)
            misc.imsave(filename, image)

            filename = parent + "ground/%04d.png" % indexes[i]
            image = disparity_images[i, :, :, :]
            image *= (self.max/self.dmax)
            image =  np.clip(image, 0.0, 1.0)
            image *= 255
            image = image.astype(np.uint8)

            size = [image.shape[0],image.shape[1]]
            image = np.reshape(image, size)
            misc.imsave(filename, image)

            filename = parent + "left/%04d.png" % indexes[i]
            image = left_images[i, :, :, :]
            plt.imsave(filename, image)

            filename = parent + "right/%04d.png" % indexes[i]
            image = right_images[i, :, :, :]
            plt.imsave(filename, image)

       
        epe = s / t 
        pix_epe = epe * self.dmax
        print("Train EPE: %f %fpix" % (epe, pix_epe))
        print("Max used: %f" % self.dmax)

        nsamples = 6
        nsamples = self.test_lx.shape[0]

        s = 0
        t = 0
        for i in range(0, nsamples, 1):
            indexes = np.arange(i, i+k)
            left_images = self.test_lx[ indexes, :, :, : ]
            right_images = self.test_rx[ indexes, :, :, : ]
            disparity_images = self.test_dx[ indexes, :, :, : ]
            predicted_disparity = self.model.predict([left_images, right_images])

            a = predicted_disparity[0, :, :, :]
            b = disparity_images[0, :, :, :]
            ab = a - b
            dim = a.shape[0]*a.shape[1]
            e = np.sum(np.absolute(ab))
            e = e.astype('float32')
            e = e/dim
            s += e
            t += 1

            if j>10:
                continue

            for i in range(k):
                if not self.predict:
                    continue
                filename = parent + "test/%04d.png" % indexes[i]
                image = predicted_disparity[i, :, :, :] 
                image *= (self.max/self.dmax)
                image =  np.clip(image, 0.0, 1.0)
                image *= 255.0
                image = image.astype(np.uint8)
                size = [image.shape[0],image.shape[1]]
                image = np.reshape(image, size)
                misc.imsave(filename, image)

                if self.i==0 and complete:
                    filename = parent + "test/ground/%04d.png" % indexes[i]
                    image = disparity_images[i, :, :, :] 
                    image *= (self.max/self.dmax)
                    image =  np.clip(image, 0.0, 1.0)
                    image *= 255
                    image = image.astype(np.uint8)
                    size = [image.shape[0],image.shape[1]]
                    image = np.reshape(image, size)
                    misc.imsave(filename, image)

                    filename = parent + "test/left/%04d.png" % indexes[i]
                    image = left_images[i, :, :, :]
                    plt.imsave(filename, image)

                    filename = parent + "test/right/%04d.png" % indexes[i]
                    image = right_images[i, :, :, :]
                    plt.imsave(filename, image)
                    plt.imsave(filename, image)


        print("dim: ", dim)
        print("count: ", t)

        ave = s/t 
        print("Test EPE: %f %fpix" % (ave, ave*self.max))
        print("Max used: %f" % self.max)

        if (self.i%10) == 0 or self.predict: 
            fd = open("flying.set.epe.txt", "a")
            log += ", test pix ave, %f, test size, %d, maxpix, %f, train epe, %f, test epe, %f\n" % (self.test_pixave, t, self.dmax, tepe, ave*self.max)
            fd.write(log)
            fd.close()
            self.s2 += s
            self.t2 += t

        self.i += 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-w", "--weights",\
                        help="Load checkpoint hdf5 file of model trained weights")
    parser.add_argument("-d", "--dataset",\
                        help="Name of dataset to load")
    parser.add_argument("-n", "--num_dataset", type=int,\
                        help="Number of  dataset file splits to load")
    
    args = parser.parse_args()
    settings = Settings()
    settings.model_weights = args.weights
    settings.dataset = args.dataset
    settings.num_dataset = args.num_dataset

    predictor = Predictor(settings=settings)
    predictor.train_network()
