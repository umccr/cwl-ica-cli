#!/usr/bin/env bash

set -euo pipefail

PAGE_SIZE=1000

if [[ -n "${ICA_ACCESS_TOKEN-}" && -n "${ICA_BASE_URL}" ]]; then

  # Get volume name and path attributes
  volume_name="$(python -c "from urllib.parse import urlparse; print(urlparse(\"${CURRENT_WORD}\").netloc)")";
  path="$(python -c "from urllib.parse import urlparse; print(urlparse(\"${CURRENT_WORD}\").path)")";

  # If volume or path is not defined, just print all of the volumes
  if [[ -z "${volume_name}" || -z "${path}" ]]; then
    curl --fail --silent --location \
      --request GET \
      --header "Accept: application/json" \
      --header "Authorization: Bearer ${ICA_ACCESS_TOKEN}" \
      --url "${ICA_BASE_URL}/v1/volumes?pageSize=${PAGE_SIZE}" | \
    jq --raw-output \
      '
        .items |
        map("gds://\(.name)/") |
        .[]
      ';
  else
    # If path attribute of url is set, call the folders api
    curl --fail --silent --location \
      --request GET \
      --header "Accept: application/json" \
      --header "Authorization: Bearer ${ICA_ACCESS_TOKEN}" \
      --url "${ICA_BASE_URL}/v1/folders?volume.name=${volume_name}&pageSize=${PAGE_SIZE}&recursive=false&path=${path}*" | \
    jq --raw-output \
      '
        .items |
        map("gds://\(.volumeName)\(.path)") |
        .[]
      ';
  fi
fi