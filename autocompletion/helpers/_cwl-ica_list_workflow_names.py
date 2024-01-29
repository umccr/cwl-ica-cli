#!/usr/bin/env python

"""
List all of the category names in the categories.yaml file
"""
# CWL ICA imports
from cwl_ica.utils.repo import get_workflow_yaml_path
from cwl_ica.utils.miscell import read_yaml

# Import yaml and print each tool name
for workflow in read_yaml(get_workflow_yaml_path())["workflows"]:
    print(workflow["name"])