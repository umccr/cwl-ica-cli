#!/usr/bin/env bash

# Set to fail
set -euo pipefail

# Globals
REQUIRED_NODE_VERSION="16.10"
REQUIRED_YARN_VERSION="1.22"

# Handy functions
echo_stderr(){
  : '
  Write out to stderr
  '
  echo "${@}" 1>&2
}

# Functions for semver
_verlte() {
  [ "$1" = "$(echo -e "$1\n$2" | sort -V | head -n1)" ]
}

_verlt() {
  [ "$1" = "$2" ] && return 1 || verlte "$1" "$2"
}

# Help function
print_help(){
  echo "Usage: initialise_typescript_expression_directory.sh (--typescript-expression-dir expression-path)
Creates an isolated yarn/ts environment ready to use and create a typescript expression in.
Required parameters:
         --typescript-expression-dir: Path to place typescript expressions
"
}

# Check jq is available
if ! type jq >/dev/null 2>&1; then
  echo_stderr "jq not installed, please ensure jq is installed"
  exit 1
fi


# Check node is available
if ! type node >/dev/null 2>&1; then
  echo_stderr "node not installed, please ensure node is installed"
  exit 1
fi

# Check yarn is available
if ! type yarn >/dev/null 2>&1; then
  echo_stderr "yarn not installed, please ensure yarn is installed"
  exit 1
fi

# Check node is greater than 16.10
if ! _verlte "${REQUIRED_NODE_VERSION}" "$(node --version | sed 's/^v//g')"; then
  echo_stderr "Your node version is too old"
  return 1
fi

# Check yarn is greater than 1.22
if ! _verlte "${REQUIRED_YARN_VERSION}" "$(yarn --version)"; then
  echo_stderr "Your yarn version is too old"
  return 1
fi

# Get arguments
typescript_expression_dir=""
# Get args from command line
while [ $# -gt 0 ]; do
  case "$1" in
    --typescript-expression-dir)
      typescript_expression_dir="$2"
      shift 1
      ;;
  esac
  shift 1
done

# Check parameter set
if [[ -z "${typescript_expression_dir}" ]]; then
  echo_stderr "Error! --typescript-expression-dir parameter found"
  print_help
  exit 1
fi

# Ensure directory does not exist but parent exists
if [[ -d "${typescript_expression_dir}" ]]; then
  echo_stderr "Error! Please ensure typescript expression directory '${typescript_expression_dir}' does not exist"
  print_help
  exit 1
fi

# Ensure parent directory exists
if [[ ! -d "$(dirname "${typescript_expression_dir}")" ]]; then
  echo_stderr "Error! Please ensure the parent directory of the typescript expression directory parameter exists '${typescript_expression_dir}'"
  exit 1
fi

# Check if we have the conda env
# value of "0" for no and "1" for yes
has_cwl_ica_conda_env="$( \
  if ! type conda; then
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

# If conda, has yarn and node as the condaenv versions
# (if they exist!)
if [[ "${has_cwl_ica_conda_env}" == "1" ]]; then
  CWL_ICA_BIN_PATH="$( \
    conda activate cwl-ica && \
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

echo "Creating typescript expression directory"
mkdir "${typescript_expression_dir}"

# Run yarn init on the directory
(
  cd "${typescript_expression_dir}" && \
  echo_stderr "Running 'yarn init -2' in '${typescript_expression_dir}'" && \
  yarn init -2 && \
  echo_stderr "Setting yarn version to stable" && \
  yarn set version stable && \
  echo_stderr "Running an installation test" && \
  yarn install && \
  echo_stderr "Checking the new version of yarn, should be >3" && \
  echo_stderr "Yarn version is '$(yarn --version)'" && \
  echo_stderr "Add project requirements" && \
  yarn add --dev \
    typescript \
    ts-jest \
    jest \
    cwl-ts-auto \
    @types/jest && \
  echo_stderr "And then subsequently delete the project so all we're left with is the yarn installation files"
  rm -rf \
    ".editorconfig" \
    ".git/" \
    "README.md" \
    ".yarn/cache" \
    ".yarn/node_modules" \
    ".yarn/unplugged"
)

# Initialising typescript project
echo_stderr "Initialising typescript project in directory"
(
  cd "${typescript_expression_dir}" && \
  {
    echo '{'
    echo '    "compilerOptions": {'
    echo '        "target": "es5",                                  /* Set the JavaScript language version for emitted JavaScript and include compatible library declarations. */'
    echo '        "module": "commonjs",                                /* Specify what module code is generated. */'
    echo '        "esModuleInterop": true,                             /* Emit additional JavaScript to ease support for importing CommonJS modules. This enables 'allowSyntheticDefaultImports' for type compatibility. */'
    echo '        "forceConsistentCasingInFileNames": true,            /* Ensure that casing is correct in imports. */'
    echo '        "strict": true,                                      /* Enable all strict type-checking options. */'
    echo '    }'
    echo '}'
  } > tsconfig.json
)

# Initialising ts-jest
echo_stderr "Initialising typescript project in directory"
(
  cd "${typescript_expression_dir}" && \
  {
    echo '{'
    echo '    "compilerOptions": {'
    echo '        "target": "es5",                                  /* Set the JavaScript language version for emitted JavaScript and include compatible library declarations. */'
    echo '        "module": "commonjs",                                /* Specify what module code is generated. */'
    echo '        "esModuleInterop": true,                             /* Emit additional JavaScript to ease support for importing CommonJS modules. This enables 'allowSyntheticDefaultImports' for type compatibility. */'
    echo '        "forceConsistentCasingInFileNames": true,            /* Ensure that casing is correct in imports. */'
    echo '        "strict": true,                                      /* Enable all strict type-checking options. */'
    echo '    }'
    echo '}'
  } > tsconfig.json
)

echo_stderr "Initialised ts-jest configuration"
(
  cd "${typescript_expression_dir}" && \
  {
    echo "/** @type {import(\'ts-jest/dist/types\').InitialOptionsTsJest} */"
    echo "module.exports = {"
    echo "  preset: 'ts-jest',"
    echo "  testEnvironment: 'node',"
    echo "  collectCoverage: true,"
    echo "  coverageReporters: ["
    echo "    \"text-summary\""
    echo "  ]"
    echo "}"
  } > jest.config.js
)

# If no conda then run yarn install in this directory
if [[ "${has_cwl_ica_conda_env}" == "0" ]]; then
  echo_stderr "Since we're not running through cwl-ica, we re-populate the package list"
  (
    cd "${typescript_expression_dir}" && \
    yarn install
  )
fi