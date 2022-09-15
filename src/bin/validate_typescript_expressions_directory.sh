#!/usr/bin/env bash

: '
Given a typescript expression directory, run the commands to validate the directory
'

REQUIRED_YARN_VERSION="1.22"
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

get_sed_binary(){
  if [[ "${OSTYPE}" == "darwin"* ]]; then
    echo "gsed"
  else
    echo "sed"
  fi
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


# Print help message
print_help(){
  echo "
        Usage: validate_typescript_expressions_directory.sh (--typescript-expressions-dir /path/to/ts/expression-dir)
                                                            [--cwlify-js-code]

        Description:
          Validate a directory containing a typescript expression for cwl.

        Options:
            --typescript-expressions-dir:          path to typescript expressions directory
            --cwlify-js-code:                      export .js code as .cwljs for appropriate import into cwl tool or expression

        Requirements:
          yarn v3+

        Environment:

        Example:
          validate_typescript_expressions_directory.sh --typescript-expressions-dir /path/to/ts/expression-dir --cwlify-js-code
        "
}


# Get args
typescript_expressions_dir=""
cwlify_js_code="false"

# Get arguments
typescript_expressions_dir=""
# Get args from command line
while [ $# -gt 0 ]; do
  case "$1" in
    --typescript-expressions-dir)
      typescript_expressions_dir="$2"
      shift 1
      ;;
    --cwlify-js-code)
      cwlify_js_code="true"
      ;;
  esac
  shift 1
done

# Run steps
echo_stderr "Running transpilation of typescript code"
(
  cd "${typescript_expressions_dir}" && \
  # Step 1 - Run transpilation through yarn dlx
  yarn dlx \
    --package typescript \
    --package ts-jest \
    --package jest \
    --package cwl-ts-auto \
    --package "@types/jest" \
    tsc
)


# Step 2 - Run validation through yarn dlx
echo_stderr "Running jest of typescript code"
(
  cd "${typescript_expressions_dir}" && \
  yarn dlx \
    --package typescript \
    --package ts-jest \
    --package jest \
    --package cwl-ts-auto \
    --package "@types/jest" \
    jest
)

# Step 3 - Convert js code to cwljs code (with sed)
if [[ "${cwlify_js_code}" == "true" ]]; then
  echo_stderr "Converting js code to cwljs code"

  # Sed logic described below
  : '
    1d removes the line use strict;
    /^exports\.*/d; removes all exports lines i.e _exports._esModule = true;
    s%//(.*)%/* \1 */%; converts single line comments (that use the // syntax) to /comment/ syntax
    s%class_%class%; converts class_ attribute to class, since cwl-ts-auto will use the class_ over class attribute
    s%:\ %:%g; converts ": " to ":" since CWL will otherwise interpret ": " as a yaml ke
  '

  # Use a while loop to stop shellcheck complaining
  # https://github.com/koalaman/shellcheck/wiki/SC2044
  (
    cd "${typescript_expressions_dir}" && \
    while IFS= read -r -d '' js_file
    do
      cwljs_file="${js_file%%.js}.cwljs"
      "$(get_sed_binary)" \
        --regexp-extended \
        --expression '
        1d;
        /^exports\.*/d;
        s%//(.*)%/* \1 */%;
        s%class_%class%;
        s%:\ %:%g;
      ' "${js_file}" > "${cwljs_file}"
    done < <(find . -name '*.ts' -print0)
  )
fi