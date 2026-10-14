#!/usr/bin/env python

"""
The ProductionProject subclass flags a project as a production project in project.yaml.

Historically it also performed ICAv1 workflow-version syncing (via libica). ICAv1 has been
deprecated, so this is now a thin subclass of Project that only sets the ``is_production``
flag used when reading / writing project.yaml.
"""

# Utils
from ..utils.logging import get_logger

# Locals
from .project import Project

# Set logger
logger = get_logger()


class ProductionProject(Project):
    """
    A production project - identical to Project other than the is_production flag,
    which is persisted to project.yaml as ``production: true``.
    """

    is_production = True  # Overwrites default in Project class
