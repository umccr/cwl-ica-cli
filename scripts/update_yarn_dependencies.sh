#!/usr/bin/env bash

set -euo pipefail

: '
Given a typescript expression directory, run yarn up "*" inside the directory to upgrade all dependencies
'

REQUIRED_YARN_VERSION="3.2"
# Functions for semver
_verlte() {
  [ "$1" = "$(echo -e "$1\n$2" | sort -V | head -n1)" ]
}

_verlt() {
  [ "$1" = "$2" ] && return 1 || verlte "$1" "$2"
}

# Handy functions
echo_stderr(){
  : '
  Write out to stderr
  '
  echo "${@}" 1>&2
}

# Check yarn is available
if ! type yarn >/dev/null 2>&1; then
  echo_stderr "yarn not installed, please ensure yarn is installed"
  exit 1
fi

# Check yarn is greater than 1.22
if ! _verlte "${REQUIRED_YARN_VERSION}" "$(yarn --version)"; then
  echo_stderr "Your yarn version is too old"
  return 1
fi

# Check rsync is installed
if ! type rsync >/dev/null 2>&1; then
  echo_stderr "rsync not installed, please ensure rsync is installed"
  exit 1
fi

# Print help message
print_help(){
  echo "
        Usage: update_yarn_dependencies.sh (--typescript-expressions-dir /path/to/ts/expression-dir)

        Description:
          Validate a directory containing a typescript expression for cwl.

        Options:
            --typescript-expressions-dir:          path to typescript expressions directory

        Requirements:
          yarn v3+

        Environment:

        Example:
          update_yarn_dependencies.sh --typescript-expressions-dir /path/to/ts/expression-dir --cwlify-js-code
        "
}


# Get args
typescript_expressions_dir=""

# Get arguments
typescript_expressions_dir=""
# Get args from command line
while [ $# -gt 0 ]; do
  case "$1" in
    --typescript-expressions-dir)
      typescript_expressions_dir="$2"
      shift 1
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      print_help
      exit 1
  esac
  shift 1
done

# Check typescript_expressions_dir exists
if [[ ! -d "${typescript_expressions_dir}" ]]; then
  echo_stderr "--typescript-expression-dir '${typescript_expressions_dir}' must exist in order to update dependencies"
  exit 1
fi

# Check yarn.lock file exists inside directory
if [[ ! -r "${typescript_expressions_dir}/yarn.lock" ]]; then
  echo_stderr "Could not find yarn.lock file inside directory '${typescript_expressions_dir}'"
  exit 1
fi


# Check if we have the conda env
# value of "0" for no and "1" for yes
has_cwl_ica_conda_env="$( \
  if ! type conda 1>/dev/null 2>&1; then
    echo "0"; \
  else
    conda env list --json | \
    jq --raw-output \
      '
        .envs |
        map(
          select(
            split("/")[-1] |
            test("^cwl-ica$")
          )
        ) |
        length
      '; \
  fi \
)"

# Step -1 - Hash the right yarn
if [[ "${has_cwl_ica_conda_env}" == "1" ]]; then
  CWL_ICA_BIN_PATH="$( \
    conda run --name "cwl-ica" && \
    sh -c "echo '${CONDA_PREFIX}/bin'" \
  )"
  if [[ -d "${CWL_ICA_BIN_PATH}" ]]; then
    # Hash yarn
    if [[ -r "${CWL_ICA_BIN_PATH}/yarn" ]]; then
      hash -p "${CWL_ICA_BIN_PATH}/yarn" "yarn"
    fi

    # Hash node
    if [[ -r "${CWL_ICA_BIN_PATH}/node" ]]; then
      hash -p "${CWL_ICA_BIN_PATH}/node" "node"
    fi
  fi
fi

# Step 0 - Copy everything to a temp directory
temp_dir="$(dirname "${typescript_expressions_dir}")/.$(basename "${typescript_expressions_dir}")-upgrade"

trap 'rm -rf "${temp_dir}"' EXIT

echo_stderr "Copying everything from '${typescript_expressions_dir}/' to '${temp_dir}/'"
rsync --archive \
  "${typescript_expressions_dir}/" "${temp_dir}/"

# Run the yarn command
(
  cd "${temp_dir}"
  echo_stderr "Running yarn up in directory '${temp_dir}'"
  yarn up '*'
)

# Re sync the yarn.lock and package.json files
echo_stderr "Syncing back the yarn.lock and package.json files"
rsync --archive \
  --prune-empty-dirs \
  --include="package.json" --include="yarn.lock" \
  --exclude="*" \
  "${temp_dir}/" "${typescript_expressions_dir}/"

# Delete temp dir
echo_stderr "Deleting temp dir '${temp_dir}'"
rm -rf "${temp_dir}"

# Exit trap
trap - EXIT
