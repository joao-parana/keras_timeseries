from __future__ import print_function
import sys
import json
import numpy as np
import pandas
import math
#import talib

seed=7
np.random.seed(seed)  # for reproducibility

from processing import *


from keras.models import Sequential
from keras.layers.core import Dense, Activation
from keras.layers import Convolution1D, MaxPooling1D
from keras.optimizers import SGD
from keras.utils import np_utils
from custom_callbacks import CriteriaStopping
from keras.callbacks import CSVLogger, EarlyStopping, ModelCheckpoint, TensorBoard
#from hyperbolic_nonlinearities import AdaptativeAssymetricBiHyperbolic, AdaptativeBiHyperbolic, AdaptativeHyperbolicReLU, AdaptativeHyperbolic, PELU
#from keras.layers.advanced_activations import ParametricSoftplus, SReLU, PReLU, ELU, LeakyReLU, ThresholdedReLU


dataframe = pandas.read_csv('ibov_google_15jun2017_1min_15d.csv', sep = ',', usecols=[1],  engine='python', skiprows=8, decimal='.',header=None)
dataset = dataframe[1].tolist()

batch_size = 128
nb_epoch = 200
patience = 50
look_back = 7

def evaluate_model(model, dataset, dadosp, name, n_layers, hals):
    X_train, X_test, Y_train, Y_test = dataset
    X_trainp, X_testp, Y_trainp, Y_testp = dadosp

    csv_logger = CSVLogger('output/%d_layers/%s.csv' % (n_layers, name))
    es = EarlyStopping(monitor='loss', patience=patience)
    #mcp = ModelCheckpoint('output/mnist_adaptative_%dx800/%s.checkpoint' % (n_layers, name), save_weights_only=True)
    #tb = TensorBoard(log_dir='output/mnist_adaptative_%dx800' % n_layers, histogram_freq=1, write_graph=False, write_images=False)

    
    sgd = SGD(lr=0.01, momentum=0.9, nesterov=True)

    optimizer = sgd
    #optimizer = "adam"
    #optimizer = "adadelta"

    model.compile(loss='mean_squared_error', optimizer=optimizer)

    # reshape input to be [samples, time steps, features]
    #X_train = np.reshape(X_train, (X_train.shape[0], 1, X_train.shape[1]))
    #X_test = np.reshape(X_test, (X_test.shape[0], 1, X_test.shape[1]))

    history = model.fit(X_train, Y_train, batch_size=batch_size, nb_epoch=nb_epoch, verbose=0, validation_split=0.1, callbacks=[csv_logger,es])

    #trainScore = model.evaluate(X_train, Y_train, verbose=0)
    #print('Train Score: %f MSE (%f RMSE)' % (trainScore, math.sqrt(trainScore)))
    #testScore = model.evaluate(X_test, Y_test, verbose=0)
    #print('Test Score: %f MSE (%f RMSE)' % (testScore, math.sqrt(testScore)))

    # make predictions
    trainPredict = model.predict(X_train)
    testPredict = model.predict(X_test)
    
    
    # invert predictions
    params = []
    for xt in X_testp:
        xt = np.array(xt)
        mean_ = xt.mean()
        scale_ = xt.std()
        params.append([mean_, scale_])

    new_predicted = []

    for pred, par in zip(testPredict, params):
        a = pred*par[1]
        a += par[0]
        new_predicted.append(a)


    params = []
    for xt in X_testp:
        xt = np.array(xt)
        mean_ = xt.mean()
        scale_ = xt.std()
        params.append([mean_, scale_])
        
    new_train_predicted= []

    for pred, par in zip(trainPredict, params):
        a = pred*par[1]
        a += par[0]
        new_train_predicted.append(a)

    # calculate root mean squared error
    trainScore = mean_squared_error(trainPredict, new_train_predicted)
    print('Train Score: %f RMSE' % (trainScore))
    testScore = mean_squared_error(testPredict, new_predicted)
    print('Test Score: %f RMSE' % (testScore))
    epochs = len(history.epoch)

    return trainScore, testScore, epochs, optimizer


def create_layer(name):
    if name == 'aabh':
        return AdaptativeAssymetricBiHyperbolic()
    elif name == 'abh':
        return AdaptativeBiHyperbolic()
    elif name == 'ah':
        return AdaptativeHyperbolic()
    elif name == 'ahrelu':
        return AdaptativeHyperbolicReLU()
    elif name == 'srelu':
        return SReLU()
    elif name == 'prelu':
        return PReLU()
    elif name == 'lrelu':
        return LeakyReLU()
    elif name == 'trelu':
        return ThresholdedReLU()
    elif name == 'elu':
        return ELU()
    elif name == 'pelu':
        return PELU()
    elif name == 'psoftplus':
        return ParametricSoftplus()
    elif name == 'sigmoid':
        return Activation('sigmoid')
    elif name == 'relu':
        return Activation('relu')
    elif name == 'tanh':
        return Activation('tanh')
    elif name == 'softplus':
        return Activation('softplus')

def __main__(argv):
    n_layers = int(argv[0])
    print(n_layers,'layers')

    #nonlinearities = ['aabh', 'abh', 'ah', 'sigmoid', 'relu', 'tanh']
    nonlinearities = ['sigmoid', 'relu', 'tanh']

    with open("output/%d_layers/compare.csv" % n_layers, "a") as fp:
        fp.write("-Convolutional NN\n")

    hals = []

    TRAIN_SIZE = 30
    TARGET_TIME = 1
    LAG_SIZE = 1
    EMB_SIZE = 1
    
    X, Y = split_into_chunks(dataset, TRAIN_SIZE, TARGET_TIME, LAG_SIZE, binary=False, scale=True)
    X, Y = np.array(X), np.array(Y)
    X_train, X_test, Y_train, Y_test = create_Xt_Yt(X, Y, percentage=0.9)

    dados = X_train, X_test, Y_train, Y_test

    Xp, Yp = split_into_chunks(dataset, TRAIN_SIZE, TARGET_TIME, LAG_SIZE, binary=False, scale=False)
    Xp, Yp = np.array(Xp), np.array(Yp)
    X_trainp, X_testp, Y_trainp, Y_testp = create_Xt_Yt(Xp, Yp, percentage=0.9)

    dadosp = X_trainp, X_testp, Y_trainp, Y_testp

    for name in nonlinearities:
        model = Sequential()

        #model.add(Dense(4, input_dim=(look_back)))
        model.add(Convolution1D(input_shape = (TRAIN_SIZE, EMB_SIZE),nb_filter=8,filter_length=12,border_mode='valid',subsample_length=4))
        model.add(MaxPooling1D(pool_length=2))
        HAL = create_layer(name)
        model.add(HAL)
        hals.append(HAL)
        for l in range(n_layers):
            model.add(Convolution1D(input_shape = (TRAIN_SIZE,EMB_SIZE),nb_filter=8,filter_length=12, border_mode='valid',subsample_length=4))
            model.add(MaxPooling1D(pool_length=2))
            HAL = create_layer(name)
            model.add(HAL)
            hals.append(HAL)
        model.add(Dense(1))
        model.add(HAL)
        model.summary()

        trainScore, testScore, epochs, optimizer = evaluate_model(model, dados, dadosp, name, n_layers, hals)

        with open("output/%d_layers/compare.csv" % n_layers, "a") as fp:
            fp.write("%s,%f,%f,%d,%s\n" % (name, trainScore, testScore, epochs, optimizer))

        model = None

if __name__ == "__main__":
   __main__(sys.argv[1:])
