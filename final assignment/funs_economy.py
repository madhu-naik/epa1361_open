# -*- coding: utf-8 -*-
"""
Created on Sun Oct 29 15:52:12 2017

@author: ciullo
"""
import numpy as np

def cost_fun(ratio, c, b, lambd, dikeinit, dikeincrease):
        ''' Cost of raising the dikes, assuming an exponential function '''
        
        dikeinit = 0 # still not clear how much the init dike height influence it - aks jarl
        dikeincrease = dikeincrease*100 # cm
        dikeinit = dikeinit*100
        
        cost = ((c + b * dikeincrease) * np.exp(lambd*(dikeinit + dikeincrease)))*ratio
        return cost*1e6

def discount(amount, rate, n):
        ''' discount function overall a planning period of n years '''

        factor = 1 + rate/100
        disc_amount = amount * 1/(np.repeat(factor,n)**(range(1,n+1)))
        return disc_amount