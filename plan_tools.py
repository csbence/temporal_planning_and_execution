#!

from textx.metamodel import metamodel_from_str
from textx.model import children_of_type

grammar = """
Model: actions*=Action;
Action: time=FLOAT ':' details=Details '[' duration=FLOAT ']' ';' '(' idk=INT ')';
Details: '(' args*=/[a-zA-Z0-9-]+/ ')';
"""

plan_metamodel = metamodel_from_str(grammar)

def plan_from_str(plan_str): return plan_metamodel.model_from_str(plan_str)


def plan_from_file(plan_path): return plan_metamodel.model_from_file(plan_path)


def plan_to_string(plan):
    plan_actions = []
    for action in plan.actions:
       args = " ".join(actions.details.args)
       plan_rows.append("{time}: ({args}) [{duration}] ; ({idk})".format(time=action.time, args=args, duration=action.duration, idk=action.idk))

    return '\n'.join(plan_rows)


def gat_from_plan(plan): return plan.actions[-1].time


def adjust_plan(plan, adjustment):
    for action in plan.actions: action.time += adjustment
