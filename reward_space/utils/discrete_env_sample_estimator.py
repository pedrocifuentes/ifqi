import numpy as np
import numpy.linalg as la
from reward_space.utils.sample_estimator import SampleEstimator

class DiscreteEnvSampleEstimator(SampleEstimator):

    def __init__(self, dataset, gamma, state_space, action_space):

        '''
        Works only for discrete mdps.
        :param dataset: numpy array (n_samples,7) of the form
            dataset[:,0] = current state
            dataset[:,1] = current action
            dataset[:,2] = reward
            dataset[:,3] = next state
            dataset[:,4] = discount
            dataset[:,5] = a flag indicating whether the reached state is absorbing
            dataset[:,6] = a flag indicating whether the episode is finished (absorbing state
                           is reached or the time horizon is met)
        :param gamma: discount factor
        :param state_space: numpy array
        :param action_space: numpy array
        '''
        self.dataset = dataset
        self.gamma = gamma
        self.state_space = state_space
        self.action_space = action_space
        self._estimate()

    def _estimate(self):
        states = self.dataset[:, 0]
        actions = self.dataset[:, 1]
        next_states = self.dataset[:, 3]
        discounts = self.dataset[:, 4]

        nS = len(self.state_space)
        nA = len(self.action_space)

        n_episodes = 0

        P = np.zeros((nS * nA, nS))
        mu = np.zeros(nS)

        d_s_mu = np.zeros(nS)
        d_sa_mu = np.zeros(nS * nA)

        d_sas2 = np.zeros((nS * nA, nS))
        d_sasa = np.zeros((nS * nA, nS * nA))
        d_sasa2 = np.zeros((nS * nA, nS * nA))

        d_sasa_mu = np.zeros((nS * nA, nS * nA))

        i = 0
        while i < self.dataset.shape[0]:
            j = i
            s_i = np.argwhere(self.state_space == states[i])
            a_i = np.argwhere(self.action_space == actions[i])
            s_next_i = np.argwhere(self.state_space == next_states[i])

            P[s_i * nA + a_i, s_next_i] += 1
            d_s_mu[s_i] += discounts[i]
            d_sa_mu[s_i * nA + a_i] += discounts[i]

            if i == 0 or self.dataset[i - 1, -1] == 1:
                mu[s_i] += 1
                n_episodes += 1

            while j < self.dataset.shape[0] and self.dataset[j, -1] == 0:
                s_j = np.argwhere(self.state_space == states[j])
                a_j = np.argwhere(self.action_space == actions[j])
                if j > i:
                    d_sas2[s_i * nA + a_i, s_j] += discounts[j] / discounts[i]
                    d_sasa2[s_i * nA + a_i, s_j * nA + a_j] += discounts[j] / \
                                                               discounts[i]
                d_sasa[s_i * nA + a_i, s_j * nA + a_j] += discounts[j] / \
                                                          discounts[i]
                d_sasa_mu[s_i * nA + a_i, s_j * nA + a_j] += discounts[j]
                j += 1

            if j < self.dataset.shape[0]:
                s_j = np.argwhere(self.state_space == states[j])
                a_j = np.argwhere(self.action_space == actions[j])
                if j > i:
                    d_sas2[s_i * nA + a_i, s_j] += discounts[j] / discounts[i]
                    d_sasa2[s_i * nA + a_i, s_j * nA + a_j] += discounts[j] / \
                                                               discounts[i]
                d_sasa[s_i * nA + a_i, s_j * nA + a_j] += discounts[j] / \
                                                          discounts[i]
                d_sasa_mu[s_i * nA + a_i, s_j * nA + a_j] += discounts[j]

            i += 1

        sa_count = P.sum(axis=1)
        self.sa_count = sa_count
        s_count = P.sum(axis=0)
        P = np.apply_along_axis(lambda x: x / (sa_count + self.tol), axis=0,
                                arr=P)

        mu /= mu.sum()

        d_s_mu /= n_episodes
        d_sa_mu /= n_episodes
        d_sas2 = d_sas2 / (sa_count[:, np.newaxis] + self.tol)
        d_sasa2 = d_sasa2 / (sa_count[:, np.newaxis] + self.tol) + np.eye(
            nS * nA)
        d_sasa /= (sa_count[:, np.newaxis] + self.tol)

        d_sasa_mu /= n_episodes

        self.P = P
        self.mu = mu
        self.d_s_mu = d_s_mu
        self.d_sa_mu = d_sa_mu
        self.d_sas2 = d_sas2
        self.d_sasa = d_sasa
        self.d_sasa2 = d_sasa2

        self.d_sasa_mu = d_sasa_mu

        self.J = 1.0 / n_episodes * np.sum(
            self.dataset[:, 2] * self.dataset[:, 4])



    def compute_PVF(self, k, operator='norm-laplacian', method='on-policy'):
        states = self.dataset[:, 0]
        actions = self.dataset[:, 1]

        nS = len(self.state_space)
        nA = len(self.action_space)

        W = np.zeros((nS * nA, nS * nA))

        i = 0
        while i < self.dataset.shape[0]:
            if self.dataset[i, -1] == 0:
                s_i = np.argwhere(self.state_space == states[i])
                a_i = np.argwhere(self.action_space == actions[i])
                s_next_i = np.argwhere(self.state_space == states[i + 1])
                a_next_i = np.argwhere(self.action_space == actions[i + 1])
                if W[s_i * nA + a_i, s_next_i * nA + a_next_i] == 0:
                    if method == 'on-policy':
                        W[s_i * nA + a_i, s_next_i * nA + a_next_i] = 1
                    elif method == 'off-policy':
                        W[s_i * nA + a_i, s_next_i * nA + self.action_space] = 1

            i = i + 1

        W = .5 * (W + W.T)

        d = W.sum(axis=1)
        D = np.diag(d)
        D1 = np.diag(np.power(d + self.tol, -0.5))

        if operator == 'norm-laplacian':
            L = la.multi_dot([D1, D - W, D1])
        elif operator == 'comb-laplacian':
            L = D - W
        elif operator == 'random-walk':
            L = la.solve(np.diag(d + self.tol), W)

        if np.allclose(L.T, L):
            eigval, eigvec = la.eigh(L)
        else:
            eigval, eigvec = la.eig(L)
            eigval, eigvec = abs(eigval), abs(eigvec)
            ind = eigval.argsort()
            eigval, eigvec = eigval[ind], eigvec[ind]

        if operator in ['norm-laplacian', 'comb-laplacian']:
            return eigval[:k], eigvec[:, :k]
        else:
            return eigval[-k:], eigvec[:, -k:]