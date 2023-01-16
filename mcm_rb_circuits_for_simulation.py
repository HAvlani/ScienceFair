#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@authors: dmckay, lcggovia
"""

'''
Code to generate the MCM RB sequences
'''
import numpy as np
from scipy.optimize import curve_fit
from qiskit.circuit import QuantumCircuit
from qiskit.quantum_info import random_clifford
from qiskit.result import marginal_counts as margct
import qiskit.quantum_info as qi
import qiskit.providers.aer.noise as noise
from qiskit import Aer


def mcm_rb_circs(xvals, seeds=1, rb_list = [],
                 ancilla_list = [],
                 make_delay_circuits = False,
                 make_mcm_only_circuits = False,
                 make_t1_check_circuits = False,
                 meas_len = 0, sqgate_len = 0,
                 add_delay = 0,
                 ancilla_excited = False):

    """
    Generate the mcm RB  sequences

    Args:
        xvals: number of cliffords
        
        seeds: number of random sequences to create 
       
        rb_list: qubits to put the cliffords on
        
        ancilla_list: qubits that are the ancilla

        make_delay_circuits: will make circuits that don't have
        the measurement, just a wait time (meas_len+add_delay)

        make_mcm_only_circuits: no random cliffords just
        idles of 'sgqate_len' and the measurements

        make_t1_check_circuits: makes a circuit with a wait time
        equal to the measurement and sqglen

        meas_len: length of the measurement (for delay circuits)
        
        sqgate_len: length of the single qubit gate (for mcm only circuits)
        
        add_delay: length of delay to add after the measurement
        
        ancilla_excited: initialize the ancilla in the excited state


    Returns:
        collected_circs: list of all the mcm circuits

    """

    collected_circs = []

    #right now, all qunitarys are just Identity gates
    #custom unitary (used for measurements)
    meas_u = qi.Operator([[1, 0, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]])

    #custom unitary (used for adding noise models)
    cust_pre_m_id = qi.Operator([[1, 0, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]])

    cust_post_m_id = qi.Operator([[1, 0, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]])

    #custom unitary (used for adding noise models)
    cust_pre_delay_id = qi.Operator([[1, 0, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]])

    cust_post_delay_id = qi.Operator([[1, 0, 0, 0],
                     [0, 1, 0, 0],
                     [0, 0, 1, 0],
                     [0, 0, 0, 1]])

    #model for measurement
    meas_channel = noise.depolarizing_error(1e-12, 1).tensor(noise.phase_damping_error(1.0))
    noise_model = noise.NoiseModel()
    for rb_q, _ in enumerate(rb_list):
        noise_model.add_quantum_error(meas_channel, ['meas_u'], [rb_q + len(rb_list),rb_q])   #makes custom error model. unsure about last line

    for seed in range(seeds):
        cliffs_all_q = {}

        #build a list of 1Q random cliffords
        #update the maximum xval length
        for rb_q, _ in enumerate(rb_list):
            cliffs = []
            for i in range(max(xvals)):
                cliffs.append(random_clifford(1))
            cliffs_all_q[rb_q] = cliffs

        q_register_size =  len(rb_list) + len(ancilla_list)

        #iterate through each xval and build the sequence
        for seq in xvals:
            qc = QuantumCircuit(q_register_size, q_register_size)
            qc.name = 'MCM_RB_seed_'+str(seed)+'_xVal_'+str(seq)
            composed = cliffs[0] # not sure what this means
            
            # initialize in excited state
            if ancilla_excited: #prob means if ancilla is at |1> state
                for anc_q, _ in enumerate(ancilla_list):
                    qc.x(anc_q+len(rb_list))

                qc.barrier()

            #these are the standard MCM circuits
            for i in range(seq):
                c = cliffs[i]

                #append the cliffords
                for rb_q, _ in enumerate(rb_list):
                    qc.append(c,[rb_q])
                qc.barrier()

                #in between the cliffords append the
                #measurement
                for anc_q, _ in enumerate(ancilla_list):

                    for rb_q, _ in enumerate(rb_list):
                        qc.unitary(cust_pre_m_id, [anc_q+len(rb_list),rb_q],label='pre_meas_id')
                        qc.unitary(meas_u, [anc_q+len(rb_list),rb_q],label='meas_u')
                        qc.unitary(cust_post_m_id, [anc_q+len(rb_list),rb_q],label='post_meas_id')

                if add_delay > 0:
                    qc.barrier()
                    qc.delay(add_delay)
                qc.barrier()

                if i>0:
                    composed = composed.compose(cliffs[i])

            #calculate inverse
            inverse_final = composed.to_circuit().inverse()

            if seq > 0:
                #append inverse
                for rb_q, _ in enumerate(rb_list):
                    qc.append(inverse_final,[rb_q])
            qc.barrier()

            qc.save_probabilities()

            for q in range(q_register_size):
                qc.measure([q], [q])

            #append the circuit
            collected_circs.append(qc)

            #if we put in a finite measurement length
            #then make a set of circuits that are
            #just a wait time
            if make_delay_circuits:

                qc = QuantumCircuit(q_register_size, q_register_size)
                qc.name = 'NoMCM_RB_seed_'+str(seed)+'_xVal_'+str(seq)
                composed = cliffs[0]
                
                # initialize in excited state
                if ancilla_excited:
                    for anc_q, _ in enumerate(ancilla_list):
                        qc.x(anc_q+len(rb_list))

                    qc.barrier()
                
                for i in range(seq):
                    c = cliffs[i]
                    for rb_q, _ in enumerate(rb_list):
                        qc.append(c,[rb_q])
                    qc.barrier()

                    for rb_q, _ in enumerate(rb_list):
                        qc.unitary(cust_pre_delay_id, [anc_q+len(rb_list),rb_q],label='pre_delay_id')

                    qc.delay(meas_len+add_delay)

                    for rb_q, _ in enumerate(rb_list):
                        qc.unitary(cust_post_delay_id, [anc_q+len(rb_list), rb_q],label='post_delay_id')

                    qc.barrier()

                    if i>0:
                        composed = composed.compose(cliffs[i])

                inverse_final = composed.to_circuit().inverse()

                if seq > 0:
                    for rb_q, _ in enumerate(rb_list):
                        qc.append(inverse_final,[rb_q])
                qc.barrier()

                qc.save_probabilities()

                for q in range(q_register_size):
                    qc.measure([q], [q])

                collected_circs.append(qc)

            if make_mcm_only_circuits:
                qc = QuantumCircuit(q_register_size, q_register_size)
                qc.name = 'MCM_noRB_seed_'+str(seed)+'_xVal_'+str(seq)
                
                # initialize in excited state
                if ancilla_excited:
                    for anc_q, _ in enumerate(ancilla_list):
                        qc.x(anc_q+len(rb_list))
                    
                    qc.barrier()

                for i in range(seq):
                    qc.delay(2*sqgate_len)
                    qc.barrier()
                    for anc_q, _ in enumerate(ancilla_list):

                        for rb_q, _ in enumerate(rb_list):
                            qc.unitary(cust_pre_m_id, [anc_q+len(rb_list),rb_q],label='pre_meas_id')
                            qc.unitary(meas_u, [anc_q+len(rb_list),rb_q],label='meas_u')
                            qc.unitary(cust_post_m_id, [anc_q+len(rb_list), rb_q],label='post_meas_id')

                    if add_delay > 0:
                        qc.barrier()
                        qc.delay(add_delay)
                    qc.barrier()

                qc.delay(2*sqgate_len)
                qc.barrier()

                qc.save_probabilities()

                for q in range(q_register_size):
                    qc.measure([q], [q])

                collected_circs.append(qc)

            if make_t1_check_circuits:

                qc = QuantumCircuit(q_register_size, q_register_size)
                qc.name = 'noMCM_noRB_seed_'+str(seed)+'_xVal_'+str(seq)
                for q in range(q_register_size):
                    qc.x(q)
                qc.barrier()
                for i in range(seq):
                    qc.delay(2*sqgate_len)
                    qc.barrier()
                    qc.delay(meas_len)
                    if add_delay > 0:
                        qc.barrier()
                        qc.delay(add_delay)
                    qc.barrier()

                for q in range(q_register_size):
                    qc.x(q)
                qc.barrier()
                for q in range(q_register_size):
                    qc.measure([q], [q])
                collected_circs.append(qc)
    print(qc)


    return collected_circs, noise_model

def expfunction_alpha(x, a, b, c):
    return a * b**x + c

def linearfunction(x, a, b):
    return -a * x + b

def fit_mcm_RB_sims(job, sqrb_list, ancilla_q_list):

    """
    Fit the mcm RB  sequences

    Args:
        job: ibmq job with the data
        sqrb_list: list of the qubits
        ancilla_q_list: list of the ancilla

    Returns:
        xvals, rb_res, fits

    """

    import re

    #pull the information from the job
    result = job.result()
    shots = result.results[0].shots
    creg_size = result.results[0].header.creg_sizes[0][1]
    num_circs = len(result.results)
    seeds = list(map(int, re.findall(r'\d+', result.results[-1].header.name)))[0]+1

    xvals = []
    for res in result.results:
        xvals.append(list(map(int, re.findall(r'\d+', res.header.name)))[1])
    xvals = np.unique(np.array(xvals))

    num_exp = int(num_circs/(len(xvals)*seeds))

    xval_allseeds = []
    for _ in range(seeds):
        for val in xvals:
            xval_allseeds.append(val)

    marg_counts = {}
    rb_res = {}
    fits = {}
    fits_linear = {}

    #extract data and fit
    if creg_size < 2:
        plotdivide = 1
    else:
        plotdivide = 2

    for splt in range(plotdivide):
        if splt == 0:
            qubitlist = sqrb_list
        else:
            qubitlist = ancilla_q_list


        for k, qlabel in enumerate(qubitlist):
            if splt > 0:
                k = k+len(sqrb_list)

            marg_counts['marg'+str(k)] = []
            for n in range(num_circs):
                marg_counts['marg'+str(k)].append(result.results[n].data.probabilities[0] + result.results[n].data.probabilities[2-k]) # this now just saves the prob of state 0, only works for 2 qubits

            for exp in range(num_exp):
                rb_res['rb_res_%d_%d'%(exp,k)] = []
                for j in range(len(result.results)):
                    if j%num_exp == exp:
                        rb_res['rb_res_%d_%d'%(exp,k)].append(marg_counts['marg'+str(k)][j])

                rescale = 1
                offset = 0
                if exp == 3:
                    rescale = 2
                    offset = 0.5

                fits['fit_%d_%d'%(exp,k)] = curve_fit(expfunction_alpha, xval_allseeds, np.array(rb_res['rb_res_%d_%d'%(exp,k)])/rescale+offset, bounds=[[0.4999,0,.4999],[0.5001,1,0.5001]],p0 = [0.5,1.0,0.5])

                fits_linear['fit_%d_%d'%(exp,k)] = curve_fit(linearfunction, xval_allseeds, np.array(rb_res['rb_res_%d_%d'%(exp,k)])/rescale+offset, bounds=[[0.,0.],[1.0,1.0]],p0 = [0.,1.0])


    print('Done')

    return xvals, rb_res, fits, fits_linear

def fit_mcm_RB_sims_free(job, sqrb_list, ancilla_q_list):
    
    """
    Fit the mcm RB  sequences 
        
    Args:
        job: ibmq job with the data
        sqrb_list: list of the qubits
        ancilla_q_list: list of the ancilla

    Returns:
        xvals, rb_res, fits  
        
    """
    
    import re
    
    #pull the information from the job
    result = job.result()
    shots = result.results[0].shots
    creg_size = result.results[0].header.creg_sizes[0][1]
    num_circs = len(result.results)
    seeds = list(map(int, re.findall(r'\d+', result.results[-1].header.name)))[0]+1
    
    xvals = []
    for res in result.results:
        xvals.append(list(map(int, re.findall(r'\d+', res.header.name)))[1])
    xvals = np.unique(np.array(xvals))
    
    num_exp = int(num_circs/(len(xvals)*seeds))
    
    xval_allseeds = []
    for _ in range(seeds):
        for val in xvals:
            xval_allseeds.append(val)

    marg_counts = {}
    rb_res = {}
    fits = {}
    fits_linear = {}
   
    #extract data and fit
    if creg_size < 2:
        plotdivide = 1
    else:
        plotdivide = 2
     
    for splt in range(plotdivide):
        if splt == 0:
            qubitlist = sqrb_list
        else:
            qubitlist = ancilla_q_list
            
        
        for k, qlabel in enumerate(qubitlist):
            if splt > 0:
                k = k+len(sqrb_list)
            
            marg_counts['marg'+str(k)] = []
            for n in range(num_circs):
                marg_counts['marg'+str(k)].append(result.results[n].data.probabilities[0] + result.results[n].data.probabilities[2-k]) # this now just saves the prob of state 0, only works for 2 qubits
                
            for exp in range(num_exp):
                rb_res['rb_res_%d_%d'%(exp,k)] = []
                for j in range(len(result.results)):
                    if j%num_exp == exp:
                        rb_res['rb_res_%d_%d'%(exp,k)].append(marg_counts['marg'+str(k)][j])
                        
                rescale = 1
                offset = 0 
                if exp == 3:
                    rescale = 2
                    offset = 0.5
                
                
                fits['fit_%d_%d'%(exp,k)] = curve_fit(expfunction_alpha, xval_allseeds, np.array(rb_res['rb_res_%d_%d'%(exp,k)])/rescale+offset, bounds=[[0.,0.,0.],[1.,1.,1.]],p0 = [0.5,1.0,0.5])
                
                fits_linear['fit_%d_%d'%(exp,k)] = curve_fit(linearfunction, xval_allseeds, np.array(rb_res['rb_res_%d_%d'%(exp,k)])/rescale+offset, bounds=[[0.,0.],[1.0,1.0]],p0 = [0.,1.0])   
          

    print('Done')
        
    return xvals, rb_res, fits, fits_linear