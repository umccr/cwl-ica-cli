#!/usr/bin/env python

# CWL ICA imports
from cwl_ica.utils.repo import get_tenant_yaml_path
from cwl_ica.utils.miscell import read_yaml

for tenant in read_yaml(get_tenant_yaml_path())["tenants"]:
    print(tenant["tenant_name"])