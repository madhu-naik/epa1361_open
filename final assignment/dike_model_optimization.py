from __future__ import (unicode_literals, print_function, absolute_import,
                                        division)


from ema_workbench import (Model, MultiprocessingEvaluator, 
                           ScalarOutcome, IntegerParameter, optimize, Scenario)
from ema_workbench.em_framework.optimization import EpsilonProgress, HyperVolume
from ema_workbench.util import ema_logging

from problem_formulation import get_model_for_problem_formulation
import matplotlib.pyplot as plt    
import seaborn as sns


if __name__ == '__main__':
    ema_logging.log_to_stderr(ema_logging.INFO)

    dike_model = get_model_for_problem_formulation(2)
    
    scen1 = {'A.2_pfail':0.5, 'A.2_Bmax':175,'A.2_Brate':1.5,'A.3_pfail':0.5,
    		  'A.3_Bmax':175,'A.3_Brate':1.5,'A.4_pfail':0.5,'A.4_Bmax':175,
    		  'A.4_Brate':1.5, 'A.5_pfail':0.5,'A.5_Bmax':175,'A.5_Brate':1.5,
            'A.1_pfail':0.5,'A.1_Bmax':175,'A.1_Brate':1.5}

    scen2 = {'A.2_pfail':0.2, 'A.2_Bmax':250,'A.2_Brate':1000,'A.3_pfail':0.2,
    		  'A.3_Bmax':250,'A.3_Brate':1000,'A.4_pfail':0.2,'A.4_Bmax':250,
    		  'A.4_Brate':1000, 'A.5_pfail':0.2,'A.5_Bmax':250,'A.5_Brate':1000,
            'A.1_pfail':0.2,'A.1_Bmax':250,'A.1_Brate':1000}

    scen3 = {'A.2_pfail':0.7, 'A.2_Bmax':30,'A.2_Brate':0.9,'A.3_pfail':0.7,
    		  'A.3_Bmax':30,'A.3_Brate':0.9,'A.4_pfail':0.7,'A.4_Bmax':30,
    		  'A.4_Brate':0.9, 'A.5_pfail':0.7,'A.5_Bmax':30,'A.5_Brate':0.9,
            'A.1_pfail':0.7,'A.1_Bmax':30,'A.1_Brate':0.9}
    
        
    ref_scenario = Scenario(**scen1)
    worst_scenario = Scenario(**scen2)
    strongdikes_scenario = Scenario(**scen3)

    convergence_metrics = [EpsilonProgress()]
    
    espilonPF2 = [1e3]*len(dike_model.levers)

    nfe = 200

# OPTIMIZATION:
#    results = optimize(dike_model, nfe=100, searchover='levers',
#                       epsilons=espilonPF2,
#                       convergence = convergence_metrics, reference = ref_scenario)
    
    with MultiprocessingEvaluator(dike_model) as evaluator:
        results, convergence = evaluator.optimize(nfe = nfe,
                                  searchover = 'levers', 
                                  epsilons = espilonPF2,
                                  convergence = convergence_metrics, 
                                  reference = ref_scenario
                                  )


    fig, (ax1, ax2) = plt.subplots(ncols=2, sharex=True)
    fig, ax1 = plt.subplots(ncols=1)
    ax1.plot(convergence.epsilon_progress)
    ax1.set_xlabel('nr. of generations')
    ax1.set_ylabel('$\epsilon$ progress')
#    ax2.plot(convergence.hypervolume)
#    ax2.set_ylabel('hypervolume')
    sns.despine()    
    
    