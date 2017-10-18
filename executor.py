#!/usr/bin/env python3

# Parameters: <domain> <problem> <domain_name> <til_adjustment>
# Implements the baseline approach: takes as input a PDDL domain and file, and
# 1. Adjusts the timestamps of the TILs by til_adjustment
# 2. Calls a planner on the new problem
# 3. Adjusts the timestamps on the resultsing plan
# 4. Calls VAL to check the new plan
# Returns 0 if this works, non-zero otherwise

from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import math
from adjust_til import adjust_til
import plan_tools
from os import path, makedirs
from subprocess import run, TimeoutExpired
import os
import sys
import resource

RESULT_DIR = 'results'
PLANNER="/home/aifs2/bence/development/projects/rewrite/build/rewrite-no-lp --real-to-plan-time-multiplier 0"
SMART_PLANNER="/home/aifs2/bence/development/projects/rewrite/build/rewrite-no-lp"
VAL="/home/aifs2/bence/development/projects/rewrite/build/VALfiles/validate"

class PlanningError(Exception):

    def __init__(self, returncode):
        self.returncode = returncode


class Configuration:

    def __init__(self, domain, problem, memory_limit, time_limit, adjustment):
        self.domain = domain
        self.problem = problem # Might be changed to the adjusted problem
        self.memory_limit = memory_limit
        self.time_limit = time_limit
        self.adjustment = adjustment
        self.domain_name = path.basename(domain) 
        self.problem_name = path.basename(problem) 


class Result:

    def __init__(self, configuration, success, error, path=None):
        self.configuration = configuration
        self.success = success
        self.error = error
        self.path = path
        self.gat = None

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return '[success: {} gat: {} error: {}]'.format(self.success, self.gat, self.error)


def create_problem_dir(domain_name, problem_name, adjustment):
    problem_dir = '/'.join([RESULT_DIR, domain_name, problem_name, str(adjustment)])
    makedirs(problem_dir, exist_ok=True)
    return problem_dir


def create_adjusted_problem(domain, problem, adjustment, problem_dir):
    adjusted_problem = problem_dir + '/adjusted.pddl' 
    adjust_til(domain, problem, adjustment, adjusted_problem)
    return adjusted_problem


def set_memory_limit(memory_limit_bytes):
    resource.setrlimit(resource.RLIMIT_AS, (memory_limit_bytes, memory_limit_bytes))


def plan(configuration, problem_dir, planner):
    command = ' '.join([
        planner, configuration.domain, configuration.problem,
        '>', problem_dir + '/planner.out', '2>', problem_dir + '/planner.error'
        ])
    completed_process = run([command], shell=True, timeout=configuration.time_limit, preexec_fn=lambda: set_memory_limit(configuration.memory_limit))
    if completed_process.returncode != 0:
        raise PlanningError(completed_process.returncode) 


def plan_smart(configuration, problem_dir):
    plan(configuration, problem_dir, SMART_PLANNER)


def plan_adjusted(configuration, problem_dir):
    plan(configuration, problem_dir, PLANNER)


def extract_plan(problem_dir):
    command = './extract.sh {}'.format(problem_dir)
    completed_process = run([command], shell=True)


def extract_and_adjust_plan(problem_dir, adjustment):
    command = './extract_adjust.sh {} {}'.format(problem_dir, adjustment)
    completed_process = run([command], shell=True)


def validate_plan(configuration, problem_dir):
    command = VAL + ' -t 0.001 {0} {1} {2}/plan > {2}/val.log'.format(configuration.domain, configuration.problem, problem_dir)
    return run([command], shell=True, timeout=configuration.time_limit).returncode == 0


def execute_configuration(configuration):
    problem_dir = create_problem_dir(configuration.domain_name, configuration.problem_name, configuration.adjustment)

    try:
       if isinstance(configuration.adjustment, int):
           # Replace problem with the adjusted problem
           configuration.problem = create_adjusted_problem(configuration.domain, configuration.problem, configuration.adjustment, problem_dir)
           planner_out_path = plan_adjusted(configuration, problem_dir)
           extract_and_adjust_plan(problem_dir, configuration.adjustment)
       else:
           plan_smart(configuration, problem_dir)
           extract_plan(problem_dir)

       success = validate_plan(configuration, problem_dir)
       return Result(configuration=configuration, success=success, error=None, path=problem_dir)
    except TimeoutExpired:
       return Result(configuration=configuration, success=False, error='TimeoutExpired')
    except PlanningError:
       return Result(configuration=configuration, success=False, error='PlanningError')


def execute_configurations(configurations, threads=1):
    progress_bar = tqdm(total=len(configurations))
    if threads == 1:
        results = []
        for configuration in configurations:
            results.append(execute_configuration(configuration))
            progress_bar.update()
        return results
    
    futures = []
    with ThreadPoolExecutor(max_workers=threads) as executor:
        for configuration in configurations:
            future = executor.submit(execute_configuration, configuration)
            future.add_done_callback(lambda _: progress_bar.update())
            futures.append(future)

    return [future.result() for future in futures]


def process_results(results):
    for result in results:
        configuration = result.configuration
        problem_dir = create_problem_dir(configuration.domain_name, configuration.problem_name, configuration.adjustment)

        if (result.success):
            plan = plan_tools.plan_from_file(problem_dir + '/plan')
            result.gat = plan_tools.gat_from_plan(plan) 
        else:
            result.gat = None

        print('domain: {domain} problem: {problem} adjustment: {adjustment} result: {result}'.format(
            domain=configuration.domain_name,
            problem=configuration.problem_name,
            adjustment=configuration.adjustment,
            result=result))

    # Plot data


def generate_configurations():
    # We probably want to replace the hardcoded parts
    domain = '/home/aifs2/bence/development/projects/temporal_planning_and_execution/resources/DOMAINS/trucks/TimeConstraints/Time-TIL/domain.pddl'
    problem = '/home/aifs2/bence/development/projects/temporal_planning_and_execution/resources/DOMAINS/trucks/TimeConstraints/Time-TIL/p07.pddl'
    memory_limit = 4 * 1024 ** 3
    time_limit = 1800
    adjustments = ['smart', 1, 10, 100, 1000]

    return [Configuration(domain=domain, problem=problem, memory_limit=memory_limit, time_limit=time_limit, adjustment=adjustment) for adjustment in adjustments]


def main():
    configurations = generate_configurations()
    results = execute_configurations(configurations, threads=5)
    process_results(results)


if __name__ == "__main__":
    main()
