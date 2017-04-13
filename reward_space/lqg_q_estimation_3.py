from __future__ import print_function
from ifqi.envs import LQG1D
from ifqi.evaluation import evaluation
import numpy as np
from numpy import linalg as LA
import ifqi.envs as envs

from policy import GaussianPolicy1D
from utils import add_discount, chebvalNd, MinMaxScaler
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

def compute_feature_matrix(n_samples, n_features, states, actions, features):
    X = np.zeros(shape=(n_samples,n_features))
    for i in range(n_samples):
        for j in range(n_features):
            X[i,j] = features[j]([states[i], actions[i]])
    return X

def remove_projections(X, C, w):
    W = np.diag(w)
    P_cx = LA.multi_dot([C.T, W, X])
    P_cc = LA.multi_dot([C.T, W, C])
    C_norms2 = np.diag(np.diag(P_cc)) 
    P_cx_n = (np.power(C_norms2,-1)).dot(P_cx)
    X_ort = X - C.dot(P_cx_n) 
    return X_ort

def find_basis(X, w):
    W = np.diag(w)
    W_inv = np.diag(np.power(w,-1))
    
    X_tilda_ort = np.sqrt(W).dot(X)
    U_ort, s_ort, V_ort = LA.svd(X_tilda_ort)
    tol = s_ort.max() * max(X_ort.shape) * np.finfo(s_ort.dtype).eps
    U_tilda_ort_ort = U_ort[:,:s_ort.shape[0]][:,s_ort > tol] 
    U_ort_ort = np.sqrt(W_inv).dot(U_tilda_ort_ort)
    return U_ort_ort

def estimate_Q(X, Q_true):
    w, residuals, rank, _ =  LA.lstsq(X, Q_true)
    rmse = np.sqrt(residuals/X.shape[0])
    Q_hat = X.dot(w)
    return Q_hat, w, rmse

mdp = LQG1D()

#MDP parameters
discount_factor = mdp.gamma
horizon = mdp.horizon
max_action = mdp.max_action
max_pos = mdp.max_pos
state_dim, action_dim, reward_dim = envs.get_space_info(mdp)

#Policy parameters
action_bounds = np.array([[-max_action], [max_action]], ndmin=2)
state_bounds = np.array([[-max_pos] , [max_pos]], ndmin=2)
K = mdp.computeOptimalK()
sigma = 0.001

policy = GaussianPolicy1D(K,sigma,action_bounds)

#Collect samples
n_episodes = 100
dataset = evaluation.collect_episodes(mdp, policy, n_episodes)
dataset = add_discount(dataset, 5, discount_factor)
states_actions = dataset[:,:2]
states = dataset[:,0]
actions = dataset[:,1]
discounts = dataset[:,-1]

print('Dataset (sigma %f) has %d samples' % (sigma, dataset.shape[0]))

#Scale data
bounds = [[-max_pos, max_pos], [-max_action ,max_action]]
scaler = MinMaxScaler(ndim=2, input_ranges=bounds)
scaled_states_actions = scaler.scale(states_actions)
scaled_states = scaled_states_actions[:,0]
scaled_actions = scaled_states_actions[:,1]

#Compute feature matrix    
complement = [lambda x : policy.gradient_log_pdf(x[0],x[1])]
max_degree = 5
degrees = [[ds,da] for ds in range(max_degree+1) for da in range(max_degree+1)]
cheb_basis = map(lambda d: lambda x: chebvalNd(x, d), degrees)

n_samples = dataset.shape[0]
n_features = len(cheb_basis)
n_complement = 1

X = compute_feature_matrix(n_samples, n_features, scaled_states, scaled_actions, cheb_basis)
C = compute_feature_matrix(n_samples, n_complement, states, actions, complement)

X_ort = remove_projections(X, C, discounts)
X_ort_ort = find_basis(X_ort, discounts)
print('Rank of feature matrix X %s/%s' % (X_ort_ort.shape[1], X.shape[1]))

#---------------------------Q-function evaluation-----------------------------
Q_true = np.array(map(lambda s,a: mdp.computeQFunction(s, a, K, np.power(sigma,2)), states, actions))
Q_hat, w, rmse = estimate_Q(X_ort_ort, Q_true)
error = np.abs(Q_true - Q_hat)
mae = np.mean(error)
error_rel = np.abs((Q_true - Q_hat)/Q_true)
mare = np.mean(error_rel)
J_true = 1/(1-discount_factor) * LA.multi_dot([C.T, np.diag(discounts), Q_true])
J_hat = 1/(1-discount_factor) * LA.multi_dot([C.T, np.diag(discounts), Q_hat])
print('Results of LS rmse = %s mae = %s mare = %s' % (rmse, mae, mare))
print('True policy gradient %s' % J_true)
print('Estimated policy gradient %s' % J_hat)

#-------------------------Plot------------------------------------------------
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.scatter(states, actions, Q_true, c='r', marker='o')
ax.scatter(states, actions, Q_hat, c='b', marker='^')
ax.set_xlabel('s')
ax.set_ylabel('a')
ax.set_zlabel('Q(s,a)')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')
ax.scatter(states, actions, error, c='g', marker='*')
ax.set_xlabel('s')
ax.set_ylabel('a')
ax.set_zlabel('error(s,a)')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.scatter(states, error, c='g', marker='*')
ax.set_xlabel('s')
ax.set_ylabel('|Q_true(s,*) - Q_hat(s,*)|')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.scatter(states, error_rel, c='g', marker='*')
ax.set_xlabel('s')
ax.set_ylabel('|Q_true(s,*) - Q_hat(s,*)|/|Q_true(s,*)|')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.scatter(states[:n_episodes], Q_true[:n_episodes], c='r', marker='o')
ax.scatter(states[:n_episodes], Q_hat[:n_episodes], c='b', marker='^')
ax.set_xlabel('s')
ax.set_ylabel('Q(s,*)')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.scatter(actions[:n_episodes], Q_true[:n_episodes], c='r', marker='o')
ax.scatter(actions[:n_episodes], Q_hat[:n_episodes], c='b', marker='^')
ax.set_xlabel('a')
ax.set_ylabel('Q(*,a)')
plt.show()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.scatter(states[:n_episodes], error_rel[:n_episodes], c='g', marker='*')
ax.set_xlabel('s')
ax.set_ylabel('|Q_true(s,*) - Q_hat(s,*)|/|Q_true(s,*)|')
plt.show()

