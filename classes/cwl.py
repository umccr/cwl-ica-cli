#!/usr/bin/env python

"""
Most of the cwl commands come in through here

Hierarchy is:

cwl object:
  - cwltool
  - cwlworkflow
  - cwlexpression
  - cwlschema -> alternate model for reading schema object
"""

from pathlib import Path
from os import environ
from utils.globals import ICAV1_CWLTOOL_VERSION, ICAV1_CWLTOOL_CONDA_ENV_NAME, LATEST_CWLTOOL_CONDA_ENV_NAME, \
    LATEST_CWLTOOL_VERSION
from utils.logging import get_logger
from utils.errors import CWLPackagingError, CWLValidationError, InvalidAuthorshipError
from tempfile import NamedTemporaryFile
import json
from utils.subprocess_handler import run_subprocess_proc
from hashlib import md5
from string import ascii_lowercase, digits
import cwl_utils.parser as parser

logger = get_logger()


class CWL:
    """
    Used for cwl files
    """

    def __init__(self, cwl_file_path: Path, name, version, cwl_type=None, create=False, user_obj=None):
        """
        All types treated the same except for schema
        :param cwl_type:  Either tool, workflow, expression or schema
        """

        self.cwl_file_path = cwl_file_path
        self.name = name
        self.version = version
        self.cwl_type = cwl_type
        self.cwl_obj = None  # Imported through cwl
        self.cwl_packed_obj = None  # Only created for validate_object and to grab authorship schemas.
        self.md5sum = None  # Packed md5sum
        self.create = create
        self.user_obj = user_obj

        # TODO - validate version -> version should be in x.y.z syntax

        # Check file exists
        if not create and not self.cwl_file_path.is_file():
            logger.error(f"Could not find file {cwl_file_path}")
            raise FileNotFoundError
        elif not create:
            self.import_cwl_yaml()
        # Create object
        else:
            self.create_object(user_obj=user_obj)

        # Check if cwl file exists - if not we create it, don't check just populate with the following
        # * user attributes
        # * ica namespace
        # See https://github.com/common-workflow-language/cwl-utils/commit/53d415cfaf2082a24bad7e5c1ceaabe8ea9a799e
        # Figure out how to also implement name spaces
        # * An empty label, id and doc
        # Make sure cwl_type attribute exists though
        # Can we do this for a record schema object?

    def __call__(self):
        """
        If we're invoking the create method then we just write out the object to the cwl_file_path
        Otherwise we validate the object
        :return:
        """
        if self.create:
            # Create user object
            self.create_object(self.user_obj)
            # Now write out the object to the file path
            self.write_object(self.user_obj)
        else:
            # Just validate the object
            self.validate_object()

    def import_cwl_yaml(self):
        """
        For all cwl files that aren't schema
        :return:
        """
        if self.cwl_type == "schema":
            # Function re-implemented in subclass
            raise NotImplementedError

        # Now import cwl object as a file
        self.cwl_obj = parser.load_document_by_uri(self.cwl_file_path.absolute().resolve().as_uri())

    def validate_object(self):
        """
        Validate should be a separate function
        For all types that aren't schema we perform the following validations
        Check user attributes are there
        Check for each input, there exists an ID, label and doc
        Check for each output, there exists an ID, label and doc
        Check DockerRequirement and ResourceRequirement are in hints (not requirements)
        Check none of the input ids are the same as the output ids

        If a workflow, we check each step recursively.
        Make sure each step conforms
        Make sure each step is not 'inline' -> force 'run:' to be a string or something

        If this is a schema object, check each field has label and doc and type (go through type attribute)
        Check namespaces and schemas
        If field attribute is a dict, iteratively check
        If subtype is a list, iteratively check through

        :return:
        """
        # Defined in subclass
        raise NotImplementedError

    def create_object(self, user_obj):
        """
        Based on
        https://github.com/common-workflow-language/cwl-utils/blob/main/create_cwl_from_objects.py

        For all requirements we add in the namespace based on the username

        For a CWL workflow we create a bareminimum inputs / outputs and steps with
        the four main requirements for a workflow,
        * InlineJavascriptRequirement
        * ScatterFeatureRequirement
        * MultipleInputFeatureRequirement
        * StepInputExpressionRequirement

        For a tool we put in an id, label and doc and
        Place the DockerRequirement and Resource Requirements in hints and add in the ilmn-tes-resources

        Expressions just need an input, output and expression with InlineJavascript Requirement set,

        For schema we create a namespace with schema assuming username has been set as well.
        :return:
        """

        # Defined in subclass
        raise NotImplementedError

    def write_object(self, user_obj):
        """
        Write out object to cwl_file_path.
        Used in the create invocation of the command
        Each write is different, this is implemented in the subclass
        :param user_obj:
        :return:
        """

        # Defined in subclass
        raise NotImplementedError

    def check_docs(self, cwl_attr_list, warning_count):
        """
        Check labels and docs for inputs, outputs or steps
        :param cwl_attr_list:
        :param warning_count:
        :return:
        """
        validation_passing = True
        # Check inputs
        for cwl_obj in cwl_attr_list:
            # Check label and doc
            if cwl_obj.label is None:
                warning_count += 1
                logger.warning(f"Issue {warning_count}: Input \"{cwl_obj.id}\" "
                               f"does not have a 'label' attribute \"{self.cwl_file_path}\"")
                validation_passing = False
            if cwl_obj.doc is None:
                warning_count += 1
                logger.warning(f"Issue {warning_count}: Input \"{cwl_obj.id}\" "
                               f"does not have a 'doc' attribute \"{self.cwl_file_path}\"")
                validation_passing = False

        return validation_passing, warning_count

    def run_cwltool_pack(self, packed_file: NamedTemporaryFile):
        """
        Pack command with cwlutils
        :return:
        """
        _return_code, _stdout, _stderr = run_subprocess_proc(
            [
                 "conda", "run",
                 "--name", ICAV1_CWLTOOL_CONDA_ENV_NAME,
                 "cwltool", "--pack", self.cwl_file_path

            ],
            capture_output=True)

        # cwltool validation failed
        if not _return_code == 0:
            raise CWLPackagingError

        with open(packed_file.name, "w") as cwl_packed_h:
            cwl_packed_h.write(json.dumps(json.loads(_stdout), indent=2, ensure_ascii=False) + "\n")

    @staticmethod
    def run_cwltool_validate(cwl_file_path: Path):
        """
        Run subprocess command ["cwltool", "--validate", "/path/to/cwl"]
        :return:
        """

        if environ.get("GIT_COMMIT_ID", None) is not None:
            logger.info("Not running cwltool --validate with ICAv1 cwltool version "
                        "in the interests of time on GitHub Actions")
        else:
            _return_code, _stdout, _stderr = run_subprocess_proc(
                [
                    "conda", "run",
                    "--name", ICAV1_CWLTOOL_CONDA_ENV_NAME,
                    "cwltool", "--validate", cwl_file_path

                ],
                capture_output=True)

            # cwltool validation failed
            if not _return_code == 0:
                logger.error(f"cwltool validate failed when run in conda environment {ICAV1_CWLTOOL_CONDA_ENV_NAME} "
                             f"with cwltool version {ICAV1_CWLTOOL_VERSION}")
                raise CWLValidationError

        _return_code, _stdout, _stderr = run_subprocess_proc(
            [
                "conda", "run",
                "--name", f"{LATEST_CWLTOOL_CONDA_ENV_NAME}",
                "cwltool", "--validate", cwl_file_path

            ],
            capture_output=True)

        # cwltool validation failed
        if not _return_code == 0:
            logger.error(f"cwltool validate failed when run in conda environment {LATEST_CWLTOOL_CONDA_ENV_NAME} "
                         f"with cwltool version {LATEST_CWLTOOL_VERSION}")
            raise CWLValidationError

    @staticmethod
    def read_packed_file(packed_file: NamedTemporaryFile):
        """
        Read a graph based packed cwl file, query
        :return:
        """

        with open(packed_file.name, 'r') as packed_h:
            cwl_packed_obj = json.load(packed_h)

        return cwl_packed_obj

    @staticmethod
    def get_packed_md5sum(packed_file: NamedTemporaryFile):
        """
        :param packed_file:
        :return:
        """

        with open(packed_file.name, 'rb') as packed_h:
            data = packed_h.read()
            md5sum = md5(data).hexdigest()
        return md5sum

    @staticmethod
    def get_author_extension_field(user_obj):
        """
        Get the author extension field from the user_obj
        :param user_obj:
        :return:
        """

        author_class = {
            "class": "s:Person",
            "s:name": user_obj.get("username"),
            "s:email": user_obj.get("email")
        }

        if user_obj.get("identifier", None) is not None:
            author_class["s:identifier"] = user_obj.get("identifier")

        return author_class

    @staticmethod
    def validate_authorship_attr(authorship_dict):
        """
        Use the packed cwl object attribute to validate the authorship attribute
        :return:
        """

        validated = True

        expected_keys = [
            'https://schema.org/name',
            'https://schema.org/email'
        ]

        # Ensure all expected keys are in the authorship keys
        if not all(map(lambda expected_key: expected_key in authorship_dict.keys(), expected_keys)):
            logger.error("Could not find all of the following attributes in the tool {expected_keys}".format(
                expected_keys=", ".join([key for key in expected_keys])
            ))
            validated = False

        if not validated:
            raise InvalidAuthorshipError

    @staticmethod
    def check_id_conformance(id_type, arg_val):
        """
        Check id for input / output step is a combination of lowercase and underscores only
        Throw warning otherwise
        :param id_type:
        :param arg_val:
        :return:
        """
        bad_chars = list(set(arg_val).difference(ascii_lowercase + digits + "_"))
        if not len(bad_chars) == 0:
            logger.warning(
                f"Found {id_type} '{arg_val}' uses chars '{', '.join(bad_chars)}' that "
                f"aren't recommended in names of {id_type}"
            )
