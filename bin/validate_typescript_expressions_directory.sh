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

# Check rsync is installed
if ! type rsync >/dev/null 2>&1; then
  echo_stderr "rsync not installed, please ensure rsync is installed"
  exit 1
fi

# Check sed/gsed is installed
if ! type "$(get_sed_binary)" >/dev/null 2>&1; then
  echo_stderr "$(get_sed_binary) not installed, please ensure $(get_sed_binary) is installed"
  exit 1
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

# Step 1 - Run installation through yarn
echo_stderr "Installing yarn temporarily into '${typescript_expressions_dir}'"
(
  set -e
  cd "${typescript_expressions_dir}"
  if ! yarn install > yarn_install.log 2>&1; then
    echo_stderr "Yarn installation failed - see logs below"
    cat yarn_install.log 1>&2
    exit 1
  else
    rm yarn_install.log
  fi
)

echo_stderr "Running transpilation of typescript code"
(
  set -e
  cd "${typescript_expressions_dir}"
  # Step 1 - Run transpilation through yarn
  echo_stderr "Running transpiliation installation in temp dir"
  yarn exec tsc
)


# Step 2 - Run validation through yarn dlx
echo_stderr "Writing out our test to 'tests/summary.txt'"

echo_stderr "Running jest of typescript code"
(
  set -e
  cd "${typescript_expressions_dir}"
  echo -e "# Test summary completed at $(date -Iseconds)\n" > "tests/summary.txt"
  yarn exec jest |& \
  tee --append "tests/summary.txt"
)

# Step 3 - Convert js code to cwljs code (with sed)
if [[ "${cwlify_js_code}" == "true" ]]; then
  echo_stderr "Converting js code to cwljs code"

  # Sed logic described below
  : '
    1d removes the line use strict;
    /^exports\.*/d; removes all exports lines i.e _exports._esModule = true;
    /*require\("cwl-ts-auto"\)*/d; removes all require lines
    /^Object\.defineProperty\(exports*/d; removes a Object definition property statement at the header
    s%//(.*)%/* \1 */%; converts single line comments (that use the // syntax) to /comment/ syntax
    s%class_%class%; converts class_ attribute to class, since cwl-ts-auto will use the class_ over class attribute
    s%:\ %:%g; converts ": " to ":" since CWL will otherwise interpret ": " as a yaml key
    s%cwl_ts_auto_1.File_class.FILE%"File"%;  Replaces the File_class enum with just "File"
    s%cwl_ts_auto_1.Directory_class.%"Directory"%;  Replaces the Directory_class enum with just "Directory"
  '

  # Use a while loop to stop shellcheck complaining
  # https://github.com/koalaman/shellcheck/wiki/SC2044
  (
    cd "${typescript_expressions_dir}"
    while IFS= read -r -d '' ts_file
    do
      cwljs_file="${ts_file%%.ts}.cwljs"
      js_file="${ts_file%%.ts}.js"
      if [[ ! -r "${js_file}" ]]; then
        continue
      fi
      "$(get_sed_binary)" \
        --regexp-extended \
        --expression '
        1d;
        /^exports\.*/d;
        /require("cwl-ts-auto")*/d;
        /^Object\.defineProperty(exports*)*/d;
        s%//(.*)%/* \1 */%;
        s%class_%class%;
        s%:\ %:%g;
        s%cwl_ts_auto_1.File_class.FILE%"File"%;
        s%cwl_ts_auto_1.Directory_class.%"Directory"%;
      ' "${js_file}" > "${cwljs_file}"
    done < <(find . -maxdepth 1 -name '*.ts' -print0)
  )
fi

echo_stderr "Deleting yarn junk"
(
  cd "${typescript_expressions_dir}"
  rm -rf \
    ".yarn/unplugged" \
    ".yarn/cache" \
    ".yarn/install-state.gz" \
    ".yarn/node_modules" \
    ".pnp."*
)