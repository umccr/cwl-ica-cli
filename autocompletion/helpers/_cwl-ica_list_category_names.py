#!/usr/bin/env python

"""
List all of the category names in the categories.yaml file
"""
from cwl_ica.utils.repo import get_category_yaml_path
from cwl_ica.utils.miscell import read_yaml

# Import yaml and print each project name
for category in read_yaml(get_category_yaml_path())["categories"]:
    print(category["name"])
