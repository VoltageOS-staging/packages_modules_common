#!/bin/bash

# Copyright (C) 2025 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

trap 'echo "An error occurred. Aborting script."' ERR

# fail if using unset variables
set -u

function usage() {
    echo "Usage: $0 <path/to/payload>" >&2
    echo "This will apply the flags from the payload file to the connected device."  >&2
    echo "The payload file is created by another program, distributed together with this tool," \
      "that will contain the information about which flags need to be set to what value." >&2
}

if [ "$#" -ne 1 ]; then
    usage
    exit 1
fi

PAYLOAD="$1"

if [ ! -f "${PAYLOAD}" ]; then
    echo "Error: '$PAYLOAD' is not a valid file." >&2
    usage
    exit 1
fi

adb root
adb wait-for-device

DEVICE_DIR=$(adb shell mktemp -d)

PAYLOAD_FILE="${DEVICE_DIR}/payload"
PROGRAM_FILE="${DEVICE_DIR}/apply_flags.sh"

adb push "${PAYLOAD}" "${PAYLOAD_FILE}"

HOST_PROGRAM_FILE=$(mktemp)

# device-side script
cat <<END > "${HOST_PROGRAM_FILE}"
  readonly INITIAL_SYNC_STATUS=\$(cmd device_config get_sync_disabled_for_tests)
  echo
  echo
  echo "Attention: the tool is disabling device_config flag sync."
  echo "When done, you might want to revert the device to the original state by calling:"
  echo "adb shell cmd device_config set_sync_disabled_for_tests \${INITIAL_SYNC_STATUS}"
  echo

  cmd device_config set_sync_disabled_for_tests persistent

  # this is not yet actually implemented
  echo I will iterate each line on file \$1
END

adb push "${HOST_PROGRAM_FILE}" "${PROGRAM_FILE}"
adb shell chmod +x "${PROGRAM_FILE}"
adb shell "${PROGRAM_FILE}" "${PAYLOAD_FILE}"

rm "${HOST_PROGRAM_FILE}"