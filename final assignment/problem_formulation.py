# -*- coding: utf-8 -*-
"""
Created on Wed Mar 21 17:34:11 2018

@author: ciullo
"""

from __future__ import (unicode_literals, print_function, absolute_import,
                                        division)

from ema_workbench import (Model, CategoricalParameter, 
                           ScalarOutcome, IntegerParameter, RealParameter)
from dike_model_function import DikeNetwork  # @UnresolvedImport


def sum_over(*args):
    return sum(args)


def get_model_for_problem_formulation(problem_formulation_id):
    ''' Prepare DikeNetwork in a way it can be input in the EMA-workbench. 
    Specify uncertainties, levers and problem formulation.
    '''
    # Load the model:
    function = DikeNetwork()
    # workbench model:
    dike_model = Model('dikesnet', function=function)

    ## Uncertainties and Levers:    
    # specify uncertainties range:
    uncert = {'Bmax': [30, 350], 'pfail': [0, 1]} # m and [.]
    cat_uncert = {'Brate' : (0.9, 1.5, 1000)}     # growth rate
    
    # specify location-related levers range:
    dike_lev = {'DikeIncrease': [0, 10]}     # dm
    dam_lev = {'DamageReduction': [0, 50]}   # % 
    
    # specify project-related levers i.e. series of Room for the River projects:
    rfr_lev = ['{}_RfR'.format(project_id) for project_id in range(0, 5)]
    
    uncertainties = []
    levers = []
    for dike in function.dikelist:
        # uncertainties in the form: locationName_uncertaintyName      
        for uncert_name in uncert.keys():
            name = "{}_{}".format(dike, uncert_name)            
            lower, upper = uncert[uncert_name]
            uncertainties.append(RealParameter(name, lower, upper))

        for uncert_name in cat_uncert.keys():
            name = "{}_{}".format(dike, uncert_name)           
            categories = cat_uncert[uncert_name]
            uncertainties.append(CategoricalParameter(name, categories))            
                                                         
        # location-related levers in the form: locationName_leversName
        for lev_name in dike_lev.keys():
            name = "{}_{}".format(dike, lev_name)
            levers.append(IntegerParameter(name, dike_lev[lev_name][0],
                                                 dike_lev[lev_name][1]))
        
        for lev_name in dam_lev.keys():
            name = "{}_{}".format(dike, lev_name)
            levers.append(RealParameter(name, dam_lev[lev_name][0],
                                              dam_lev[lev_name][1]))
            
    # project-related levers can be either 0 (not implemented) or 1 (implemented)
    for lev_name in rfr_lev:
         levers.append(IntegerParameter(lev_name, 0, 2))    
    
    # load uncertainties and levers in dike_model:
    dike_model.uncertainties = uncertainties
    dike_model.levers = levers
    
    
    ## Problem formulations:
    # Outcomes are all costs, thus they have to minimized:
    direction = ScalarOutcome.MINIMIZE
    
    # One-objective PF:
    if problem_formulation_id == 0:
        dikes_variable_names = []
        
        for dike in function.dikelist:    
          dikes_variable_names.extend(
             ['{}_{}'.format(dike, e) for e in ['Expected Annual Damage', 
                                                'Dike Investment Costs']])
        dikes_variable_names.extend(['RfR Total Costs'])
          
        dike_model.outcomes = [ScalarOutcome('All Costs',
                               variable_name=[var for var in dikes_variable_names], 
                               function=sum_over, kind=direction)]           
    # Two-objectives PF:
    elif problem_formulation_id == 1:
        dike_model.outcomes = [
          ScalarOutcome('Expected Annual Damage', 
                        variable_name=['{}_Expected Annual Damage'.format(dike) 
                                                for dike in function.dikelist],
                        function=sum_over, kind=direction),
                        
          ScalarOutcome('Investment Costs', 
                        variable_name=['{}_Dike Investment Costs'.format(dike) 
                         for dike in function.dikelist] + ['RfR Total Costs'],
                        function=sum_over, kind=direction)]
          
    # Six-objectives PF:                                
    elif problem_formulation_id == 2:
        outcomes = []
        
        for dike in function.dikelist:
            o = ScalarOutcome('{} Total Costs'.format(dike),
                              variable_name = ['{}_{}'.format(dike, e) 
                                              for e in ['Expected Annual Damage', 
                                                        'Dike Investment Costs']],
                              function=sum_over, kind=direction)
            outcomes.append(o)
            
        outcomes.append(ScalarOutcome('RfR Total Costs', kind = direction))
        dike_model.outcomes = outcomes            

    # Eleven-objectives PF:                                                  
    elif problem_formulation_id == 3:
        outcomes = []
        
        for dike in function.dikelist:
            for entry in ['Expected Annual Damage', 'Dike Investment Costs']:
                o = ScalarOutcome('{}_{}'.format(dike, entry), kind=direction)
                outcomes.append(o)
        
        outcomes.append(ScalarOutcome('RfR Total Costs', kind = direction))
        dike_model.outcomes = outcomes
    else:
        raise TypeError('unknonw identifier')
    return dike_model