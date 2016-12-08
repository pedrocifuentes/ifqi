import numpy as np
from sklearn.ensemble import ExtraTreesRegressor

from ifqi import envs
import ifqi.evaluation.evaluation as evaluate
from ifqi.fqi.FQI import FQI
from ifqi.models.mlp import MLP
from ifqi.models.regressor import Regressor
from gym.spaces import prng
import random

import argparse


parser = argparse.ArgumentParser(
    description='Execution of one experiment thread provided a configuration file and\n\t A regressor (index)\n\t Size of dataset (index)\n\t Dataset (index)')


ranges = {
    "n_epochs": (20,2000),
    "activation": (0,3),
    "batch_size": (100,1000),
    "n_neurons": (5,100),
    "n_layers": (1,3)
}

parser.add_argument("env_name", type=str, help="Provide the environment")
parser.add_argument("n_epochs", type=int, help="Provide the size of the population")
parser.add_argument("activation", type=int, help="Provides the number of core to use")
parser.add_argument("batch_size", type=int, help="Provides the number of core to use")
parser.add_argument("n_neurons", type=int, help="Provides the number of core to use")
parser.add_argument("n_layers", type=int, help="Provides the number of core to use")
#parser.add_argument("input_scaled", type=int, help="Provides the number of core to use")
#parser.add_argument("output_scaled", type=int, help="Provides the number of core to use")



args = parser.parse_args()

env_name = args.env_name
nEpochs = args.n_epochs
activation = args.activation
batchSize = args.batch_size
nNeurons = args.n_neurons
nLayers = args.n_layers
input_scaled = True #args.input_scaled
output_scaled = True #args.output_scaled

act = "sigmoid"
if activation==1:
    act="tanh"
elif activation==2:
    act="relu"

"""Easy function
print -((-nEpochs + 520)**2 + 1) * ((- nNeurons + 21)**2 + 1)
"""

prng.seed(0)
np.random.seed(0)
random.seed(0)

sizeDS = None
if env_name=="SwingPendulum":
    sizeDS = 2000
    mdp = envs.SwingPendulum()
    discrete_actions = [-5.,5.]
elif env_name=="Acrobot":
    sizeDS = 2000
    mdp = envs.Acrobot()
    discrete_actions = mdp.action_space.values
elif env_name=="LQG1D":
    sizeDS = 5
    mdp = envs.LQG1D()
    discrete_actions = [-5.,-2.5,-1.,-0.5, 0., 0.5, 1., 2.5, 5]
elif env_name=="LQG1DD":
    sizeDS = 5
    mdp = envs.LQG1D(discrete_reward=True)
    discrete_actions = [-5.,-2.5,-1.,-0.5, 0., 0.5, 1., 2.5, 5]

mdp.seed(0)

state_dim, action_dim = envs.get_space_info(mdp)

regressor_params = {"n_input": state_dim+action_dim,
                    "n_output": 1,
                    "optimizer": "rmsprop",
                     "activation": act,
                     "hidden_neurons":[ nNeurons]*nLayers}



#ExtraTreeEnsemble
#regressor = Ensemble(ens_regressor_class=ExtraTreesRegressor, **regressor_params)

#ExtraTreeEnsemble con Regressor
#regressor_params["input_scaled"]=True
#regressor_params["output_scaled"]=False
#regressor = Ensemble(ens_regressor_class=Regressor, regressor_class=ExtraTreesRegressor, **regressor_params)

#ExtraTree con Regressor:
regressor_params["input_scaled"]= input_scaled==1
regressor_params["output_scaled"]= output_scaled==1
regressor = Regressor(regressor_class=MLP, **regressor_params)

#ExtraTree senza regressor
#regressor = ExtraTreesRegressor(**regressor_params)

#Ensemble con action regressor , con regressor e ExtraTrees
#regressor_params["input_scaled"]=True
#regressor_params["output_scaled"]=False
#regressor = ActionRegressor(model=Ensemble, discrete_actions=discrete_actions,decimals=5,ens_regressor_class=Regressor, regressor_class=ExtraTreesRegressor, **regressor_params)


state_dim, action_dim = envs.get_space_info(mdp)
reward_idx = state_dim + action_dim
dataset = evaluate.collect_episodes(mdp,policy=None,n_episodes=sizeDS)
sast = np.append(dataset[:, :reward_idx], dataset[:, reward_idx + 1:], axis=1)
sastFirst, rFirst = sast, dataset[:, reward_idx]

fqi = FQI(estimator=regressor,
          state_dim=state_dim,
          action_dim=action_dim,
          discrete_actions=discrete_actions,
          gamma=mdp.gamma,
          horizon=mdp.horizon,
          features=None,
          verbose=True)


fitParams = {
     "nb_epoch": nEpochs,
     "batch_size": batchSize,
     "verbose": False
}
fqi.partial_fit(sastFirst[:], rFirst[:], **fitParams)

iterations = 3

for i in range(iterations - 1):
    fqi.partial_fit(None, None, **fitParams)

if env_name == "LQG1D" or env_name=="LQG1DD":
    initial_states = np.zeros((5, 1))
    initial_states[:, 0] = np.linspace(-10,10,5)
    score, stdScore, step, stdStep = evaluate.evaluate_policy(mdp, fqi, 1,
                                                              initial_states=initial_states)
elif env_name == "Acrobot":
    initial_states = np.zeros((5, 4))
    initial_states[:, 0] = np.linspace(-2, 2, 5)
    score, stdScore, step, stdStep = evaluate.evaluate_policy(mdp, fqi, 41,
                                                              initial_states=initial_states)
elif env_name == "SwingPendulum":
    initial_states = np.zeros((5, 2))
    initial_states[:, 0] = np.linspace(-np.pi, np.pi, 5)
    score, stdScore, step, stdStep = evaluate.evaluate_policy(mdp, fqi, 21,
                                                              initial_states=initial_states)

print(score)

