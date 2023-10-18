#!/usr/bin/env bash

# Set to fail
set -euo pipefail

# Globals
REQUIRED_NODE_VERSION="16.10"
REQUIRED_YARN_VERSION="1.22"
STABLE_YARN_VERSION="stable"

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
  echo "
Usage: initialise_typescript_expression_directory.sh (--typescript-expression-dir expression-path)
    Creates an isolated yarn/ts environment ready to use and create a typescript expression in.

Required parameters:
         --typescript-expression-dir: Path to place typescript expressions
         --package-name: Simple place holder for the name attribute in the package.json file

Optional parameters:
         --node-linker: One of 'node-modules' or 'pnp'
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

# Check rsync is installed
if ! type rsync >/dev/null 2>&1; then
  echo_stderr "rsync not installed, please ensure rsync is installed"
  exit 1
fi


# Get arguments
typescript_expression_dir=""
package_name=""
node_linker=""
# Get args from command line
while [ $# -gt 0 ]; do
  case "$1" in
    --typescript-expression-dir)
      typescript_expression_dir="$2"
      shift 1
      ;;
    --package-name)
      package_name="$2"
      shift 1
      ;;
    --node-linker)
      node_linker="$2"
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

# Check parameter set
if [[ -z "${typescript_expression_dir}" ]]; then
  echo_stderr "Error! --typescript-expression-dir parameter found"
  print_help
  exit 1
fi

if [[ -z "${package_name}" ]]; then
  typescript_expression_dir_basename="$(basename "${typescript_expression_dir}")"
  if [[ ! "${typescript_expression_dir_basename}" == "typescript-expressions" ]]; then
    package_name="${typescript_expression_dir_basename}"
  else
    name="$(basename "$(dirname "$(dirname "${typescript_expression_dir}")")")"
    version="$(basename "$(dirname "${typescript_expression_dir}")")"
    package_name="${name}__${version}"
  fi
fi

# Ensure directory does not exist but parent exists or if directory exists it's empty
if [[ -d "${typescript_expression_dir}" && "$(find "${typescript_expression_dir}" -maxdepth 0 -not -empty -exec echo {} \; | wc -l)" -gt "0" ]]; then
  echo_stderr "Error! Please ensure typescript expression directory '${typescript_expression_dir}' does not exist"
  print_help
  exit 1
fi

# Ensure parent directory exists
if [[ ! -d "$(dirname "${typescript_expression_dir}")" ]]; then
  echo_stderr "Error! Please ensure the parent directory of the typescript expression directory parameter exists '${typescript_expression_dir}'"
  exit 1
fi

echo "Creating typescript expression directory"
mkdir -p "${typescript_expression_dir}"

cd "${typescript_expression_dir}"

# Run yarn init in a temp directory
echo_stderr "Running 'yarn init -2' in '${typescript_expression_dir}'" && \
yarn init -2 && \

echo_stderr "Setting yarn version to stable" && \
yarn set version "${STABLE_YARN_VERSION}" && \

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
  cwlts \
  @types/jest \
  @types/node && \
yarn install && \

# Initialise the .yarnrc.yml file
echo_stderr "Initialising the .yarnrc.yml file"
(
  {
    echo "nodeLinker: ${node_linker}"
  } > .yarnrc.yml
)

# Update the package name
echo_stderr "Update the package name and licensing inside package.json"
jq --raw-output \
 --arg name "${package_name}" \
 --arg license "MIT" \
 '
   .name = $name |
   .license = $license
 ' < package.json > package.json.tmp && \
mv package.json.tmp package.json

# Initialising typescript project
echo_stderr "Initialising typescript project in directory"
(
  {
    echo '{'
    echo '    "compilerOptions": {'
    echo '        "target": "es5",                                     /* Set the JavaScript language version for emitted JavaScript and include compatible library declarations. */'
    echo '        "module": "commonjs",                                /* Specify what module code is generated. */'
    echo '        "esModuleInterop": true,                             /* Emit additional JavaScript to ease support for importing CommonJS modules. This enables "allowSyntheticDefaultImports" for type compatibility. */'
    echo '        "forceConsistentCasingInFileNames": true,            /* Ensure that casing is correct in imports. */'
    echo '        "strict": true,                                      /* Enable all strict type-checking options. */'
    echo '    }'
    echo '}'
  } > tsconfig.json
)

echo_stderr "Initialised ts-jest configuration"
(
  {
    echo "/** @type {import(\'ts-jest/dist/types\').InitialOptionsTsJest} */"
    echo "module.exports = {"
    echo "  preset: 'ts-jest',"
    echo "  testEnvironment: 'node',"
    echo "  testRegex: \"(tests/.*|(\\.|/)(test|spec))\\.(ts|js)x?$\","
    echo "  collectCoverage: true,"
    echo "  coverageReporters: ["
    echo "    \"text-summary\""
    echo "  ]"
    echo "}"
  } > jest.config.js
)

# Create the tests directory too
mkdir -p "${typescript_expression_dir}/tests"