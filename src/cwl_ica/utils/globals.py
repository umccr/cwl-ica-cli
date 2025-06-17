#!/usr/bin/env python3

"""
List of globals
"""

# External imports
from enum import Enum
import re

EMAIL_REGEX = r"^(\w|\.|\_|\-)+[@](\w|\_|\-|\.)+[.]\w{2,3}$"
CWL_ICA_REPO_ACTIVATE_D_FILENAME = "cwl-ica-repo-path.sh"
CWL_ICA_REPO_PATH_ENV_VAR = "CWL_ICA_REPO_PATH"
ICA_BASE_URL_ENV_VAR = "ICA_BASE_URL"
EXPIRY_DAYS_WARNING_TRIGGER = 7
BASE_URL_NETLOC_REGEX = r"(\S+).platform.illumina.com"
PROJECT_ID_REGEX = "[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
YAML_INDENTATION_LEVEL = 4
BLOCK_YAML_INDENTATION_LEVEL = 2

GITHUB_DEFAULT_BRANCH = "main"

SCOPES_BY_ROLE = {
    "read-only": [
        "TES.RUNS.READ",
        "TES.TASKS.READ",
        "TES.VERSIONS.READ",
        "WES.RUNS.READ",
        "WES.SIGNALS.READ",
        "WES.VERSIONS.READ",
        "WES.WORKFLOWS.READ"
    ],
    # Contributor has the same roles as ica roles as an admin
    "admin": [
        # Removed ability to create/edit task runs
        "TES.RUNS.READ",
        "TES.TASKS.CREATE",
        "TES.TASKS.DELETE",
        "TES.TASKS.GRANT",
        "TES.TASKS.READ",
        "TES.TASKS.UPDATE",
        "TES.VERSIONS.CREATE",
        "TES.VERSIONS.DELETE",
        "TES.VERSIONS.GRANT",
        "TES.VERSIONS.READ",
        "TES.VERSIONS.UPDATE",
        # Removed ability to create/edit workflow runs
        "WES.RUNS.READ",
        "WES.SIGNALS.CREATE",
        "WES.SIGNALS.DELETE",
        "WES.SIGNALS.GRANT",
        "WES.SIGNALS.READ",
        "WES.SIGNALS.UPDATE",
        "WES.VERSIONS.CREATE",
        "WES.VERSIONS.DELETE",
        "WES.VERSIONS.GRANT",
        "WES.VERSIONS.READ",
        "WES.VERSIONS.UPDATE",
        "WES.WORKFLOWS.CREATE",
        "WES.WORKFLOWS.DELETE",
        "WES.WORKFLOWS.GRANT",
        "WES.WORKFLOWS.READ",
        "WES.WORKFLOWS.UPDATE"
    ]
}

ICA_TES_INSTANCE_SIZES_BY_TYPE = {
    "standard": {
        "small": {
            "cpu": 0.8,
            "memory": 3
        },
        "medium": {
            "cpu": 1.3,
            "memory": 4.5
        },
        "large": {
            "cpu": 2,
            "memory": 7
        },
        "xlarge": {
            "cpu": 4,
            "memory": 14
        },
        "xxlarge": {
            "cpu": 8,
            "memory": 28
        }
    },
    "standardHiCpu": {
        "small": {
            "cpu": 15.5,
            "memory": 28
        },
        "medium": {
            "cpu": 35.5,
            "memory": 68
        },
        "large": {
            "cpu": 71.5,
            "memory": 140
        },
    },
    "standardHiMem": {
        "small": {
            "cpu": 7.5,
            "memory": 60
        },
        "medium": {
            "cpu": 15.5,
            "memory": 124
        },
        "large": {
            "cpu": 47.5,
            "memory": 380
        },
        "xlarge": {
            "cpu": 95.5,
            "memory": 764
        }
    },
    "standardHighIo": {
        "small": {
            "cpu": 11.5,
            "memory": 92
        },
    },
    "fpga": {
        "small": {
            "cpu": 7.5,
            "memory": 118
        },
        "medium": {
            "cpu": 15.5,
            "memory": 240
        },
        "large": {
            "cpu": 63.5,
            "memory": 972
        }
    }
}

ICAV1_CWLTOOL_VERSION = "3.0.20201203173111"
ICAV1_CWLTOOL_CONDA_ENV_NAME = "cwltool-icav1"

LATEST_CWLTOOL_VERSION = "__LATEST_CWLTOOL_VERSION__"
LATEST_CWLTOOL_CONDA_ENV_NAME = "cwl-ica"

ICAV2_COMPUTE_RESOURCE_TYPE_MAPPINGS = [
    {
        "v1": "standardHiCpu",
        "v2": "hicpu"
    },
    {
        "v1": "standardHiMem",
        "v2": "himem"
    }
]

ICAV2_COMPUTE_RESOURCE_STANDARD_SIZE_MAPPINGS = [
    {
        "v1": "ilmn-tes:resources/size: medium",
        "v2": "ilmn-tes:resources/size: small"
    },
    {
        "v1": "ilmn-tes:resources/size: large",
        "v2": "ilmn-tes:resources/size: small"
    },
    {
        "v1": "ilmn-tes:resources/size: xlarge",
        "v2": "ilmn-tes:resources/size: medium"
    },
    {
        "v1": "ilmn-tes:resources/size: xxlarge",
        "v2": "ilmn-tes:resources/size: large"
    }
]

#     '3.8.4': '699120554104.dkr.ecr.us-east-1.amazonaws.com/public/dragen:3.8.4',
#     '3.9.5': '079623148045.dkr.ecr.us-east-1.amazonaws.com/cp-prod/b3403184-9116-44d1-b273-0fbe45dac466:latest',
#     '3.10.4': '079623148045.dkr.ecr.us-east-1.amazonaws.com/cp-prod/084b1d0d-3593-4e02-bac5-419425a4075d:latest',
#     '4.0.3': '079623148045.dkr.ecr.us-east-1.amazonaws.com/cp-prod/7ecddc68-f08b-4b43-99b6-aee3cbb34524:latest'

ICAV2_CONTAINER_MAPPINGS = [
    {
        "v1": "699120554104.dkr.ecr.us-east-1.amazonaws.com/public/dragen:3.8.4",
        "v2": "699120554104.dkr.ecr.us-east-1.amazonaws.com/public/dragen:3.8.4"
    },
    {
        "v1": "699120554104.dkr.ecr.us-east-1.amazonaws.com/public/dragen:3.9.3",
        "v2": "699120554104.dkr.ecr.us-east-1.amazonaws.com/public/dragen:3.9.3",
    },
    {
        "v1": "699120554104.dkr.ecr.us-east-1.amazonaws.com/public/dragen:4.0.3",
        "v2": "079623148045.dkr.ecr.us-east-1.amazonaws.com/cp-prod/7ecddc68-f08b-4b43-99b6-aee3cbb34524:latest"
    }
]

ICAV2_DRAGEN_TEMPSPACE_MAPPINGS = {
    "v1": "\"/ephemeral/\"",
    "v2": "\"/scratch/\""
}

MATCH_RUN_LINE_REGEX_OBJ = re.compile(r"run: (/)?([^/\0]+(/)?)+$")
MATCH_SCHEMA_LINE_REGEX_OBJ = re.compile(r"((?:- \$import:)|(?:type:)|(?:-)) ((/)?([^/\0#]+(/)?)+)(?:#*)")
MATCH_INCLUDE_LINE_REGEX_OBJ = re.compile(r"(?:- \$include): ((/)?([^/\0]+(/)?)+)")

PARAMS_XML_FILE_NAME = "params.xml"

BLANK_PARAMS_XML_V2_FILE_CONTENTS = [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<pd:pipeline xmlns:pd="xsd://www.illumina.com/ica/cp/pipelinedefinition" code="" version="1.0">',
    '    <pd:dataInputs/>',
    '    <pd:steps/>',
    '</pd:pipeline>'
]

ICAV2_MAX_STEP_CHARACTERS = 23

ICAV2_DEFAULT_BASE_URL = "https://ica.illumina.com/ica/rest"


class ICAv2AnalysisStorageSize(Enum):
    SMALL = "Small"
    MEDIUM = "Medium"
    LARGE = "Large"


ICAV2_DEFAULT_ANALYSIS_STORAGE_SIZE = ICAv2AnalysisStorageSize.SMALL
