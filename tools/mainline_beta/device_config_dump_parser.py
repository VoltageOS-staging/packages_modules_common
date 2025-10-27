#!/usr/bin/env python3
#
# Copyright (C) 2025 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import argparse
import re
import sys
from typing import TextIO

# Regex to match lines like "namespace/key=value"
# Group 1: namespace
# Group 2: key
# Group 3: value
_FLAG_LINE_REGEX=re.compile(r"^([^/]+)/([^=]+)=(true|false)$")


def is_start_of_flags(line: str) -> bool:
  """Detects if the line appears to be the start of the list of flags.

  This can be either the device_config section in a whole dumpsys dump,
  or the start of the output of `adb shell dumpsys device_config`.
  """
  return line == "DUMP OF SERVICE device_config" or line == "DeviceConfig flags:"


def is_end_of_dumpsys(line: str) -> bool:
  """Detects if the line appears to be the end of the device_config dumpsys section."""
  return "duration of dumpsys device_config" in line


def parse_device_config_dumpsys(
    config_file: TextIO,
) -> list[dict]:
  """Parses DeviceConfig dumpsys output and extracts flag information.

  It will only return flags that have a value of either true or false.
  Everything else will be ignored.

  Args:
      config_file: A file object for the DeviceConfig dump.

  Returns:
      list: A list of dictionaries, where each dictionary represents a flag
            with 'namespace', 'key', and 'value'.
  """
  parsed_flags = []
  found_start = False

  try:
    for line in config_file:
      line = line.strip()

      if not line:
        continue

      if not found_start:
        if is_start_of_flags(line):
          found_start = True
        continue

      # check if we got to the end of the device_config dumpsys block
      if is_end_of_dumpsys(line):
        return parsed_flags

      # We can get all sorts of text from the output. Including values that span multiple lines, etc.
      # We can only do a best-effort to recognise the things that look like flags and ignore the rest.
      match = _FLAG_LINE_REGEX.match(line)
      if match:
        namespace, key, value = match.groups()
        parsed_flags.append(
            {"namespace": namespace, "key": key, "value": value}
        )
  except Exception as e:
    print(f"An error occurred while reading the file: {e}", file=sys.stderr)
    sys.exit(1)

  return parsed_flags


def main():
  parser = argparse.ArgumentParser(
      description="Parse a DeviceConfig dumpsys file and extract flag information."
  )
  parser.add_argument(
      "file",
      help="Path to the DeviceConfig dump file. Use '-' for stdin.",
      type=argparse.FileType("r", encoding="utf-8"),
  )

  args = parser.parse_args()

  with args.file as file:
    flags = parse_device_config_dumpsys(file)
    if flags:
      print("Parsed DeviceConfig Flags:")
      for flag in flags:
        print(
            f"  Namespace: {flag['namespace']}, Key: {flag['key']}, Value:"
            f" {flag['value']}"
        )
    else:
      print(
          "No DeviceConfig flags found in the file matching the expected format."
      )


if __name__ == "__main__":
  main()
