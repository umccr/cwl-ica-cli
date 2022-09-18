#!/usr/bin/env python3

"""
Helpers for creating / appending typescript interfaces
"""

from pathlib import Path
from utils.logging import get_logger
from utils.subprocess_handler import run_subprocess_proc

logger = get_logger()


def run_typescript_validation_script(typescript_expression_dir: Path):
        logger.info("Running validate_typescript_expressions_directory.sh script")
        command_list = [
            "validate_typescript_expressions_directory.sh",
            "--typescript-expressions-dir", f"{typescript_expression_dir}",
            "--cwlify-js-code"
        ]
        returncode, stdout, stderr = run_subprocess_proc(
            command_list,
            capture_output=True
        )

        print(stdout, stderr)

        if not returncode == 0:
            logger.error(f"validation of typescript expression failed with returncode '{returncode}'\n"
                         f"stdout was '{stdout}'\n"
                         f"stderr was '{stderr}'")
            raise AssertionError
        else:
            logger.info("validation of typescript expression directory command finished successfully")
            logger.info(f"stdout was '{stdout}'")
            logger.info(f"stderr was '{stderr}'")


def create_typescript_expression_dir(typescript_expression_path: Path):
    """
    Run subprocess on command initialise_typescript_expression_directory.sh
    With the --typescript-expression-dir argument set to as the parent of the cwl_file_path attribute
    :return:
    """
    command_list = [
        "initialise_typescript_expression_directory.sh",
        "--typescript-expression-dir", str(typescript_expression_path.parent)
    ]
    logger.info(f"Running the following command to initialise the typescript expression directory '{' '.join(command_list)}'")
    return_code, stdout, stderr = run_subprocess_proc(
        command_list,
        capture_output=True
    )

    if not return_code == 0:
        logger.error(f"Error initialising typescript expression directory!, return code was {return_code} "
                     f"Stdout was '{stdout}', stderr was '{stderr}'")
        raise AssertionError
    else:
        logger.info("initialise typescript expression directory command finished successfully")
        logger.info(f"stdout was '{stdout}'")
        logger.info(f"stderr was '{stderr}'")


def create_blank_typescript_file(typescript_file_path: Path, username: str):
    """
    Create blank typescript file
    :return:
    """
    with open(typescript_file_path, "w") as ts_handler:
        ts_handler.write(
            f"// Author: {username}\n"
            "// For assistance on generation of typescript expressions\n"
            "// In CWL, please visit our wiki page at https://github.com/umccr/cwl-ica/wiki/TypeScript\n"
            "// Imports\n"
            "\n"
            "// Backward compatibility with --target es5"
            "declare global {\n"
            "    interface Set<T> {\n"
            "    }\n"
            "\n"
            "    interface Map<K, V> {\n"
            "    }\n"
            "\n"
            "    interface WeakSet<T> {\n"
            "    }\n"
            "\n"
            "    interface WeakMap<K extends object, V> {\n"
            "    }\n"
            "}\n"
            "\n"
            "// Functions\n"
            "\n"
        )


def create_blank_typescript_test_file(typescript_file_path: Path, username: str):
    """
    Create a blank typescript test file
    :return:
    """

    default_test_path = typescript_file_path.parent / "tests" / (typescript_file_path.stem + ".test.ts")

    with open(default_test_path, "w") as ts_handler:
        ts_handler.write(
            f"// Author: {username}\n"
            "// For assistance on generation of typescript expression tests\n"
            "// In CWL, visit our wiki page at https://github.com/umccr/cwl-ica/wiki/TypeScript\n"
            "// Imports\n"
            "\n"
            "\n"
            "// Dummy Test\n"
            "describe('This is a dummy test', function() {\n"
            "    test('This test always passes', () => {{\n"
            "        expect(0).toEqual(0)\n"
            "    })\n"
            "})\n"
        )
