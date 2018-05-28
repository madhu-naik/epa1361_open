# -*- coding: utf-8 -*-
"""
Created on Tue Oct 31 13:18:05 2017

@author: ciullo
"""
from __future__ import division
from copy import deepcopy
from ema_workbench import ema_logging

import funs_generate_network
from funs_dikes import Lookuplin, dikefailure, init_node
from funs_economy import cost_fun, discount, cost_evacuation
from funs_hydrostat import werklijn_cdf, werklijn_inv
import numpy as np
import pandas as pd


def Muskingum(C1, C2, C3, Qn0_t1, Qn0_t0, Qn1_t0):
    ''' Simulates hydrological routing '''
    Qn1_t1 = C1 * Qn0_t1 + C2 * Qn0_t0 + C3 * Qn1_t0
    return Qn1_t1


class DikeNetwork(object):
    def __init__(self):
        # load network
        G, dike_list, dike_branch = funs_generate_network.get_network()

        # Load hydrological statistics:
        A = pd.read_excel('./data/hydrology/werklijn_params.xlsx')

        lowQ, highQ = werklijn_inv([0.992, 0.99992], A)
        Qpeaks = np.unique(np.asarray(
            [np.random.uniform(lowQ, highQ) / 6 for _ in range(0, 30)]))[::-1]

        # Probabiltiy of exceedence for the discharge @ Lobith (i.e. times 6)
        p_exc = 1 - werklijn_cdf(Qpeaks * 6, A)

        self.Qpeaks = Qpeaks
        self.p_exc = p_exc
        self.A = A
        self.G = G
        self.dikelist = dike_list
        self.dike_branch = dike_branch

        # Accounting for the discharge reduction due to upstream dike breaches
        self.sb = False

        # Planning window [y]
        self.n = 50

        # Step of dike increase [cm]
        self.step = 10

        # Time step correction: Q is a mean daily value expressed in m3/s
        self.timestepcorr = 24 * 60 * 60
        ema_logging.info('model initialized')

    # Initialize hydrology at each node:
    def _initialize_hydroloads(self, node, time, Q_0):
        node['cumVol'], node['wl'], node['Qpol'], node['hbas'] = (
            init_node(0, time) for _ in range(4))
        node['Qin'], node['Qout'] = (init_node(Q_0, time) for _ in range(2))
        node['status'] = init_node(False, time)
        node['tbreach'] = np.nan
        return node

    def _initialize_rfr_ooi(self, G, dikenodes):
        for n in dikenodes:
            node = G.node[n]
            # Create a copy of the rating curve that will be used in the sim:
            node['rnew'] = deepcopy(node['r'])

            # Initialize outcomes of interest (ooi):
            node['losses'] = []
            node['deaths'] = []
            node['evacuation_costs'] = []

        # Initialize room for the river
        G.node['RfR_projects']['cost'] = 0
        return G

    def __call__(self, timestep=1, **kwargs):

        G = self.G
        Qpeaks = self.Qpeaks
        step = self.step
        dikelist = self.dikelist

        # Call RfR initialization:
        self._initialize_rfr_ooi(G, dikelist)

        # Load all kwargs into network. Kwargs are uncertainties and levers:
        for item in kwargs:
            # when item is 'discount rate':
            if item == 'discount rate':
                G.node[item]['value'] = kwargs[item]
            # the rest of the times you always get a string like {}_{}:
            else:
                #                print(item)
                string1, string2 = item.split('_')

                if string2 == 'RfR':
                    # string1: projectID
                    # string2: rfr
                    # Note: kwargs[item] in this case can be either 0
                    # (no project) or 1 (yes project)

                    proj_node = G.node['RfR_projects']
                    # Cost of RfR project
                    proj_node['cost'] += kwargs[item] * proj_node[string1][
                        'costs_1e6'] * 1e6

                    # Iterate over the location affected by the project
                    for key in proj_node[string1].keys():
                        if key != 'costs_1e6':
                            # Change in rating curve due to the RfR project
                            G.node[key]['rnew'][:, 1] -= kwargs[item] * proj_node[
                                string1][key]
                else:
                    # string1: dikename or EWS
                    # string2: name of uncertainty or lever
                    G.node[string1][string2] = kwargs[item]

                    if string2 == 'DikeIncrease':

                        node = G.node[string1]
                        # Rescale according to step and tranform in meters
                        node[string2] = (kwargs[item] * step) / 100.0
                        # Initialize fragility curve:
                        node['fnew'] = deepcopy(node['f'])
                        # Shift it to the degree of dike heigthening:
                        node['fnew'][:, 0] += node[string2]

                        # Calculate dike heigheting costs:
                        if node[string2] == 0:
                            node['dikecosts'] = 0
                        else:
                            node['dikecosts'] = cost_fun(
                                node['traj_ratio'],
                                node['c'],
                                node['b'],
                                node['lambda'],
                                node['dikelevel'],
                                node[string2])

        # Percentage of people which cant be evacuated for a given warning
        # time:
        G.node['EWS']['evacuation_percentage'] = G.node['EWS']['evacuees'][
            G.node['EWS']['DaysToThreat']]

        # Dictionary storing outputs:
        data = {}

        for Qpeak in Qpeaks:
            node = G.node['A.0']
            waveshape_id = node['ID flood wave shape']

            time = np.arange(0, node['Qevents_shape'].loc[waveshape_id].shape[0],
                             timestep)
            node['Qout'] = Qpeak * node['Qevents_shape'].loc[waveshape_id]

            # Initialize hydrological event:
            for key in dikelist:
                node = G.node[key]

                Q_0 = int(G.node['A.0']['Qout'][0])

                self._initialize_hydroloads(node, time, Q_0)
                # Calculate critical water level: water above which failure
                # occurs
                node['critWL'] = Lookuplin(node['fnew'], 1, 0, node['pfail'])

            # Run the simulation:
            # Run over the discharge wave:
            for t in range(1, len(time)):
                # Run over each node of the branch:
                for n in range(0, len(dikelist)):
                    # Select current node:
                    node = G.node[dikelist[n]]
                    if node['type'] == 'dike':

                        # Muskingum parameters:
                        C1 = node['C1']
                        C2 = node['C2']
                        C3 = node['C3']

                        prec_node = G.node[node['prec_node']]
                        # Evaluate Q coming in a given node at time t:
                        node['Qin'][t] = Muskingum(C1, C2, C3,
                                                   prec_node['Qout'][t],
                                                   prec_node['Qout'][t - 1],
                                                   node['Qin'][t - 1])

                        # Transform Q in water levels:
                        node['wl'][t] = Lookuplin(
                            node['rnew'], 0, 1, node['Qin'][t])

                        # Evaluate failure and, in case, Q in the floodplain and
                        # Q left in the river:
                        res = dikefailure(self.sb,
                                          node['Qin'][t], node['wl'][t],
                                          node['hbas'][t], node['hground'],
                                          node['status'][t - 1], node['Bmax'],
                                          node['Brate'], time[t],
                                          node['tbreach'], node['critWL'])

                        node['Qout'][t] = res[0]
                        node['Qpol'][t] = res[1]
                        node['status'][t] = res[2]
                        node['tbreach'] = res[3]

                        # Evaluate the volume inside the floodplain as the integral
                        # of Q in time up to time t.
                        node['cumVol'][t] = np.trapz(
                            node['Qpol']) * self.timestepcorr

                        Area = Lookuplin(node['table'], 4, 0, node['wl'][t])
                        node['hbas'][t] = node['cumVol'][t] / float(Area)

                    elif node['type'] == 'downstream':
                        node['Qin'] = G.node[dikelist[n - 1]]['Qout']

            # Iterate over the network and store outcomes of interest for a
            # given event
            for dike in self.dikelist:
                node = G.node[dike]

                # If breaches occured:
                if node['status'][-1] == True:
                    # Losses per event:
                    node['losses'].append(Lookuplin(node['table'],
                                                    6, 4, np.max(node['wl'])))

                    node['deaths'].append(Lookuplin(node['table'],
                                                    6, 3, np.max(node['wl'])) * (
                        1 - G.node['EWS']['evacuation_percentage']))

                    node['evacuation_costs'].append(cost_evacuation(Lookuplin(
                        node['table'], 6, 5, np.max(node['wl'])
                    ) * G.node['EWS']['evacuation_percentage'],
                        G.node['EWS']['DaysToThreat']))
                else:
                    node['losses'].append(0)
                    node['deaths'].append(0)
                    node['evacuation_costs'].append(0)

        EECosts = []
        # Iterate over the network,compute and store ooi over all events
        for dike in dikelist:
            node = G.node[dike]

            # Expected Annual Damage:
            EAD = np.trapz(node['losses'], self.p_exc)
            # Discounted annual risk per dike ring:
            disc_EAD = np.sum(discount(EAD, rate=G.node['discount rate']['value'],
                                       n=self.n))

            # Expected Annual number of deaths:
            END = np.trapz(node['deaths'], self.p_exc)

            # Expected Evacuation costs: depend on the event, the higher
            # the event, the more people you have got to evacuate:
            EECosts.append(np.trapz(node['evacuation_costs'], self.p_exc))

            data.update({'{}_Expected Annual Damage'.format(dike): disc_EAD,
                         '{}_Expected Number of Deaths'.format(dike): END,
                         '{}_Dike Investment Costs'.format(dike): node['dikecosts']})

        data.update({'RfR Total Costs': G.node['RfR_projects']['cost']})
        data.update({'Expected Evacuation Costs': np.sum(EECosts)})

        return data
