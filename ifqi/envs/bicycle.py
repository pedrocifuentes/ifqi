#
# Copyright (C) 2013, Will Dabney
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import numpy
from environment import Environment

class Bicycle(Environment):
    """Bicycle balancing/riding domain.
    From the paper:
    Learning to Drive a Bicycle using Reinforcement Learning and Shaping.
    Jette Randlov and Preben Alstrom. 1998.
    """

    name = "Bicycle"

    def __init__(self, **kwargs):
        
        self.state_dim = 5
        self.action_dim = 1        
        self.n_states = 0
        self.n_actions = 9
        self.horizon = 1000
        self.gamma = 0.98
        
        self._noise = kwargs.setdefault('noise', 0.04)
        self._random_start = kwargs.setdefault('random_start', False)
        
        #select psi or psi_goal
        self._reward_function_psi = kwargs.setdefault('reward_function_psi', True)
        
        #select if to have uniform random psi at start or a choice between 9 different psi
        self._uniform_psi = kwargs.setdefault('uniform_psi', True)
        
        self._state = numpy.zeros((5,)) # omega, omega_dot, omega_ddot, theta, theta_dot
        self._position = numpy.zeros((5,)) # x_f, y_f, x_b, y_b, psi
        self._state_range = numpy.array([[-numpy.pi * 12./180., numpy.pi * 12./180.],
                                        [-numpy.pi * 2./180., numpy.pi * 2./180.],
                                        [-numpy.pi, numpy.pi],
                                        [-numpy.pi * 80./180., numpy.pi * 80./180.],
                                        [-numpy.pi * 2./180., numpy.pi * 2./180.]])
        self._psi_range = numpy.array([-numpy.pi, numpy.pi])

        self._reward_fall = -1.0
        self._reward_goal = 0.01
        self._goal_rsqrd = 100.0 # Square of the radius around the goal (10m)^2
        self._navigate = kwargs.setdefault('navigate', True)
        """if not self.navigate:
            # Original balancing task
            self.reward_shaping = 0.001
        else:
            self.reward_shaping = 0.00004"""
        self._reward_shaping = 0.

        self._goal_loc = numpy.array([1000., 0])

        # Units in Meters and Kilograms
        self._c = 0.66       # Horizontal dist between bottom of front wheel and center of mass
        self._d_cm = 0.30    # Vertical dist between center of mass and the cyclist
        self._h = 0.94       # Height of the center of mass over the ground
        self._l = 1.11       # Dist between front tire and back tire at point on ground
        self._M_c = 15.0     # Mass of bicycle
        self._M_d = 1.7      # Mass of tire
        self._M_p = 60       # Mass of cyclist
        self._r = 0.34       # Radius of tire
        self._v = 10.0 / 3.6 # Velocity of bicycle (converted from km/h to m/s)

        # Useful precomputations
        self._M = self._M_p + self._M_c
        self._Inertia_bc = (13./3.) * self._M_c * self._h**2 + self._M_p * (self._h + self._d_cm)**2
        self._Inertia_dv = self._M_d * self._r**2
        self._Inertia_dl = .5 * self._M_d * self._r**2
        self._sigma_dot = self._v / self._r

        # Simulation Constants
        self._gravity = 9.8
        self._delta_time = 0.01#0.02
        self._sim_steps = 1#10
        
        self._absorbing=False
        self._theta=0

    def _reset(self, state=None):
        self._absorbing=False

        psi=0        
        """if self.uniform_psi:
            psi = numpy.random.rand() * 2*numpy.pi - numpy.pi
        else:
            psi = [-numpy.pi, - 0.75 * numpy.pi , -0.5 * numpy.pi, -0.25 * numpy.pi, 0 ,numpy.pi, 0.75 * numpy.pi , 0.5 * numpy.pi, 0.25 * numpy.pi ][numpy.random.randint(9)]
        """
        self._state.fill(0.0)
        self._position.fill(0.0)
        self._position[2] = self._l * numpy.cos(psi)
        self._position[3] = self._l * numpy.sin(psi)
        self._position[4] = psi#numpy.arctan((self.position[1]-self.position[0])/(self.position[2] - self.position[3]))


    def _step(self, intAction, render=False):
        T = 2. * ((int(intAction)/3) - 1) # Torque on handle bars
        d = 0.02 * ((intAction % 3) - 1) # Displacement of center of mass (in meters)
        #if self.noise > 0:
        #    d += (numpy.random.random()-0.5)*self.noise # Noise between [-0.02, 0.02] meters

        omega, omega_dot, omega_ddot, theta, theta_dot = tuple(self._state)
        x_f, y_f, x_b, y_b, psi = tuple(self._position)

        goal_angle_old = self._angle_between(self._goal_loc, numpy.array([x_f-x_b, y_f-y_b])) * numpy.pi / 180.
        if x_f==x_b and y_f-y_b < 0:
            old_psi = numpy.pi
        elif y_f - y_b > 0:
            old_psi = numpy.arctan((x_b - x_f)/(y_f - y_b))
        else:
            old_psi = numpy.sign(x_b - x_f)*(numpy.pi/2.) - numpy.arctan((y_f - y_b)/(x_b-x_f))
                
        for step in range(self._sim_steps):
            if theta == 0: # Infinite radius tends to not be handled well
                r_f = r_b = r_CM = 1.e8
            else:
                r_f = self._l / numpy.abs(numpy.sin(theta))
                r_b = self._l / numpy.abs(numpy.tan(theta)) #self.l / numpy.abs(numpy.tan(from pyrl.misc import matrixtheta))
                r_CM = numpy.sqrt((self._l - self._c)**2 + (self._l**2 / numpy.tan(theta)**2))

            varphi = omega + numpy.arctan(d / self._h)

            omega_ddot = self._h * self._M * self._gravity * numpy.sin(varphi)
            omega_ddot -= numpy.cos(varphi) * (self._Inertia_dv * self._sigma_dot * theta_dot + numpy.sign(theta)*self._v**2*(self._M_d * self._r *(1./r_f + 1./r_b) + self._M*self._h/r_CM))
            omega_ddot /= self._Inertia_bc

            theta_ddot = (T - self._Inertia_dv * self._sigma_dot * omega_dot) / self._Inertia_dl

            df = (self._delta_time / float(self._sim_steps))
            omega_dot += df * omega_ddot
            omega += df * omega_dot
            theta_dot += df * theta_ddot
            theta += df * theta_dot

            # Handle bar limits (80 deg.)
            theta = numpy.clip(theta, self._state_range[3,0], self._state_range[3,1])

            # Update position (x,y) of tires
            front_term = psi + theta + numpy.sign(psi + theta)*numpy.arcsin(self._v * df / (2.*r_f))
            back_term = psi + numpy.sign(psi)*numpy.arcsin(self._v * df / (2.*r_b))
            x_f += -numpy.sin(front_term)
            y_f += numpy.cos(front_term)
            x_b += -numpy.sin(back_term)
            y_b += numpy.cos(back_term)

            # Handle Roundoff errors, to keep the length of the bicycle constant
            dist = numpy.sqrt((x_f-x_b)**2 + (y_f-y_b)**2)
            if numpy.abs(dist - self._l) > 0.01:
                x_b += (x_b - x_f) * (self._l - dist)/dist
                y_b += (y_b - y_f) * (self._l - dist)/dist

            # Update psi
            if x_f==x_b and y_f-y_b < 0:
                psi = numpy.pi
            elif y_f - y_b > 0:
                psi = numpy.arctan((x_b - x_f)/(y_f - y_b))
            else:
                psi = numpy.sign(x_b - x_f)*(numpy.pi/2.) - numpy.arctan((y_f - y_b)/(x_b-x_f))
            
        self._state = numpy.array([omega, omega_dot, omega_ddot, theta, theta_dot])
        self._position = numpy.array([x_f, y_f, x_b, y_b, psi])

        if numpy.abs(omega) > self._state_range[0,1]: # Bicycle fell over
            self._absorbing = True
            return -1.0
        elif self._isAtGoal():
            self._absorbing = True
            return self._reward_goal
        elif not self._navigate:
            self._absorbing = False 
            return self._reward_shaping
        else:
            goal_angle = self._angle_between(self._goal_loc, numpy.array([x_f-x_b, y_f-y_b])) * numpy.pi / 180.
            
            self._absorbing = False            
            #return (4. - goal_angle**2) * self.reward_shaping
            #ret =  0.1 * (self.angleWrapPi(old_psi) - self.angleWrapPi(psi))  
            ret =  0.1 * (self._angleWrapPi(goal_angle_old) - self._angleWrapPi(goal_angle))  
            return ret
    
    def _unit_vector(self, vector):
        """ Returns the unit vector of the vector.  """
        return vector / numpy.linalg.norm(vector)

    def _angle_between(self, v1, v2):
        """ Returns the angle in radians between vectors 'v1' and 'v2'::
    
                >>> angle_between((1, 0, 0), (0, 1, 0))
                1.5707963267948966
                >>> angle_between((1, 0, 0), (1, 0, 0))
                0.0
                >>> angle_between((1, 0, 0), (-1, 0, 0))
                3.141592653589793
        """
        v1_u = self._unit_vector(v1)
        v2_u = self._unit_vector(v2)
        return numpy.arccos(numpy.clip(numpy.dot(v1_u, v2_u), -1.0, 1.0))
    
    def _isAtGoal(self):
        # Anywhere in the goal radius
        if self._navigate:
            return numpy.sqrt(max(0.,((self._position[:2] - self._goal_loc)**2).sum() - self._goal_rsqrd)) < 1.e-5
        else:
            return False

    def _getState(self):
        omega, omega_dot, omega_ddot, theta, theta_dot = tuple(self._state)
        x_f, y_f, x_b, y_b, psi = tuple(self._position)
        goal_angle = self._angle_between(self._goal_loc, numpy.array([x_f-x_b, y_f-y_b])) * numpy.pi / 180.
        """ modified to follow Ernst paper"""
        return [omega, omega_dot, theta, theta_dot, goal_angle]
        
    def _angleWrapPi(self, x):
        while (x < -numpy.pi):
    		x += 2.0*numpy.pi
        while (x > numpy.pi):
    		x -= 2.0*numpy.pi
        return x
        
    def evaluate(self, fqi, expReplay=False, render=False):
        """
        This function evaluates the regressor in the provided object parameter.
        This way of evaluation is just one of many possible ones.
        Params:
            fqi (object): an object containing the trained regressor.
        Returns:
            a numpy array containing the average score obtained starting from
            289 different states
        
        """
        self._reset()
        J, step, goal = self._runEpisode(fqi, expReplay, render)
               
        #(J, step, goal)
        return (J, step, goal)
        