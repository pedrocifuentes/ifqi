from __future__ import print_function

import os
import sys
sys.path.append(os.path.abspath('../'))

import unittest
import numpy as np
from ifqi.fqi.FQI import FQI
from ifqi.models.mlp import MLP
from ifqi.preprocessors.mountainCarPreprocessor import MountainCarPreprocessor
from ifqi.envs.mountainCar import MountainCar
import ifqi.utils.parser as parser
from sklearn.ensemble import ExtraTreesRegressor

import matplotlib.pyplot as plt
plt.style.use('ggplot')

def runEpisode(myfqi, environment, gamma):   # (nstep, J, success)
    J = 0
    t = 0
    test_succesful = 0
    rh = []
    while(t < 500 and not environment.isAbsorbing()):
        state = environment.getState()
        action, _ = myfqi.predict(np.array(state))
        position, velocity, r = environment.step(action)
        J += gamma ** t * r
        t += 1
        rh += [r]
        
        if r == 1:
            print('Goal reached\n')
            test_succesful = 1
            
    return (t, J, test_succesful), rh

if __name__ == '__main__':

    data, sdim, adim, rdim = parser.parseReLeDataset('../dataset/mountainCar.txt')
    assert(sdim == 2)
    assert(adim == 1)
    assert(rdim == 1)

    rewardpos = sdim + adim
    indicies = np.delete(np.arange(data.shape[1]), rewardpos)

    # select state, action, nextstate, absorbin
    sast = data[:, indicies]

    prep = MountainCarPreprocessor()
    sast[:,:3] = prep.preprocess(sast[:,:3])

    # select reward
    r = data[:, rewardpos]

    estimator = 'mlp'
    if estimator == 'extra':
        alg = ExtraTreesRegressor(n_estimators=50, criterion='mse',
                                         min_samples_split=4, min_samples_leaf=2)
        fit_params = dict()
    elif estimator == 'mlp':
        alg = MLP(n_input=sdim+adim, n_output=1, hidden_neurons=10, h_layer=2,
                  optimizer='rmsprop', act_function="relu").getModel()
        fit_params = {'nb_epoch':20, 'batch_size':50, 'verbose':1}
        # it is equivalente to call
        #fqi.fit(sast,r,nb_epoch=12,batch_size=50, verbose=1)
    else:
        raise ValueError('Unknown estimator type.')

    actions = 2
    fqi = FQI(estimator=alg,
              stateDim=sdim, actionDim=adim,
              discrete_actions=actions,
              gamma=0.95, horizon=10, verbose=1)
    #fqi.fit(sast, r, **fit_params)

    environment = MountainCar()

    for t in range(100):
        fqi.partial_fit(sast, r, **fit_params)
        mod = fqi.estimator
        ## test on the simulator
        print('Simulate on environment')
        environment.reset()
        tupla, rhistory = runEpisode(fqi, environment, environment.gamma)
        #plt.scatter(np.arange(len(rhistory)), np.array(rhistory))
        #plt.show()