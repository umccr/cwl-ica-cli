#!/usr/bin/env python

"""
List all of the run instance ids in the run.yaml file
"""
# CWL ICA imports
from cwl_ica.utils.repo import get_run_yaml_path
from cwl_ica.utils.miscell import read_yaml

# Import yaml and print each run instance id
for run in read_yaml(get_run_yaml_path())["runs"]:
    print(run.get("ica_workflow_run_instance_id"))
