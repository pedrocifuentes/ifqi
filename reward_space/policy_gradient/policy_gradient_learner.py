import numpy.linalg as la
import numpy as np
from ifqi.evaluation import evaluation
import copy

class PolicyGradientLearner(object):

    '''
    This class performs policy search exploiting the policy gradient. Policy
    parameters are optimized using simple gradient ascent.
    '''

    def __init__(self,
                 mdp,
                 policy,
                 lrate=0.01,
                 lrate_decay=None,
                 estimator='reinforce',
                 max_iter_eval=100,
                 tol_eval=1e-5,
                 max_iter_opt=100,
                 tol_opt=1e-5,
                 verbose=0):

        '''
        Constructor

        param mdp: the Markov Decision Process
        param policy: the policy whose parameters are optimized
        param lrate: the learning rate
        param lrate_decay: the decay factor, currently not implemented
        param estimator: the name of the gradient estimtor to use, currently
                         only 'reinforce' is supported
        param max_iter_eval: the maximum number of iteration for gradient
                             estimation
        param tol_eval: the estimation stops when norm-2 of the gradient
                        increment is below tol_eval
        param max_iter_opt: the maximum number of iteration for gradient
                             optimization
        param tol_opt: the optimization stops when norm-2 of the gradient
                       increment is below tol_eval
        param verbose: verbosity level
        '''

        self.mdp = mdp
        self.policy = copy.deepcopy(policy)
        self.lrate = lrate
        self.lrate_decay = lrate_decay
        self.max_iter_eval = max_iter_eval
        self.tol_eval = tol_eval
        self.max_iter_opt = max_iter_opt
        self.tol_opt = tol_opt
        self.verbose = verbose

        if estimator == 'reinforce':
            self.estimator = ReinforceGradientEstimator(self.mdp,
                                                        self.policy,
                                                        self.tol_eval,
                                                        self.max_iter_eval,
                                                        self.verbose == 2)
        else:
            raise NotImplementedError()

    def optimize(self, theta0, reward=None, return_history=False):
        '''
        This method performs simple gradient ascent optimization of the policy
        parameters.

        param theta0: the initial value of the parameter
        return: the optimal value of the parameter
        '''

        ite = 0
        theta = np.array(theta0, ndmin=2)

        if return_history:
            history = [np.copy(theta)]


        self.policy.set_parameter(theta)
        self.estimator.set_policy(self.policy)

        if self.verbose >= 1:
            print('Policy gradient: starting optimization...')

        gradient = self.estimator.estimate(reward=reward)
        gradient_norm = la.norm(gradient)
        lrate = self.lrate

        if self.verbose >= 1:
            print('Ite %s: gradient norm %s' % (ite, gradient_norm))

        while gradient_norm > self.tol_opt and ite < self.max_iter_opt:
            #print(theta)
            theta += lrate * gradient  #Gradient ascent update

            if return_history:
                history.append(np.copy(theta))

            self.policy.set_parameter(theta)
            self.estimator.set_policy(self.policy)

            gradient = self.estimator.estimate(reward=reward)
            gradient_norm = la.norm(gradient)
            ite += 1

            if self.lrate_decay is not None:
                decay = self.lrate_decay['decay']
                method = self.lrate_decay['method']
                if method == 'exponential':
                    lrate *= np.exp(- ite * decay)
                elif method == 'inverse':
                    lrate = self.lrate / (1. + decay * ite)
                else:
                    raise NotImplementedError()

            if self.verbose >= 1:
                print('Ite %s: gradient norm %s' % (ite, gradient_norm))

        if return_history:
            return theta, history
        else:
            return theta

class GradientEstimator(object):
    '''
    Abstract class for gradient estimators
    '''

    eps = 1e-24  # Tolerance used to avoid divisions by zero

    def __init__(self,
                 mdp,
                 policy,
                 tol=1e-5,
                 max_iter=100,
                 verbose=True):
        '''
        Constructor

        param mdp: the Markov Decision Process
        param policy: the policy used to collect samples
        param tol: the estimation stops when norm-2 of the gradient increment is
                   below tol
        param max_iter: the maximum number of iterations for the algorithm
        param verbose: whether to display progressing messages
        '''

        self.mdp = mdp
        self.policy = policy
        self.tol = tol
        self.max_iter = max_iter
        self.dim = policy.get_dim()
        self.verbose = verbose

    def set_policy(self, policy):
        self.policy = policy

    def estimate(self, reward=None):
       pass


class ReinforceGradientEstimator(GradientEstimator):

    '''
    This class implements the Reinforce algorithm for gradient estimation with
    element wise optimal baseline

    Williams, Ronald J. "Simple statistical gradient-following algorithms for
    connectionist reinforcement learning." Machine learning 8.3-4 (1992): 229-256.
    '''

    def estimate(self, use_baseline=True, reward=None):
        '''
        This method performs gradient estimation with Reinforce algorithm.

        param use_baseline: whether to use the optimal baseline to estimate
                            the gradient
        param reward: if set, it is used in place of the reward provided by the
                      mdp to compute the gradient
        return: the estimated gradient
        '''

        if self.verbose:
            print('\tReinforce: starting estimation...')

        ite = 0
        gradient_increment = np.inf
        gradient_estimate = np.inf

        # (n_episodes, 1) vector of the trajectory returns
        traj_return = np.ndarray((0, 1))

        # (n_episodes, dim) matrix of the tragectory log policy gradient
        traj_log_grad = np.ndarray((0, self.dim))

        while ite < self.max_iter and gradient_increment > self.tol:
            ite += 1

            # Collect a trajectory
            traj = evaluation.collect_episode(self.mdp, self.policy)

            # Compute the trajectory return
            if reward is None:
                t_return = np.sum(traj[:, 2] * traj[:, 4])
            else:
                t_return = np.sum(reward(traj) * traj[:, 4])
            traj_return = np.concatenate([traj_return, [[t_return]]])

            # Compute the trajectory log policy gradient
            t_log_gradient = np.sum(
                self.policy.gradient_log(traj[:, 0], traj[:, 1], type_='list'),
                axis=0)
            traj_log_grad = np.concatenate([traj_log_grad, [t_log_gradient]])

            # Compute the optimal baseline
            if use_baseline:
                baseline = np.array(
                           np.sum(traj_log_grad ** 2 * traj_return, axis=0) / \
                           (self.eps + np.sum(traj_log_grad ** 2, axis=0)), ndmin=2)
            else:
                baseline = 0.

            # Compute the gradient estimate
            old_gradient_estimate = gradient_estimate
            gradient_estimate = 1. / ite * np.sum(
                traj_log_grad * (traj_return - baseline), axis=0)[:, np.newaxis]

            # Compute the gradient increment
            gradient_increment = la.norm(
                gradient_estimate - old_gradient_estimate)

            if self.verbose:
                print('\tIteration %s return %s gradient_norm %s gradient_increment %s' % (ite, t_return, la.norm(gradient_estimate), gradient_increment))

        return gradient_estimate

class GMDPGradientEstimator(GradientEstimator):

    def estimate(self, reward=None):
       raise NotImplementedError()

class NaturalGradientEstimator(GradientEstimator):

    def estimate(self, reward=None):
        raise NotImplementedError()

