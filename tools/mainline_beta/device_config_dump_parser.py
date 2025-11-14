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
import io
import re
import sys
from typing import TextIO
import zipfile


_verbose: bool = False

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
          if _verbose:
            print("Found start of section")
        continue

      # check if we got to the end of the device_config dumpsys block
      if is_end_of_dumpsys(line):
        if _verbose:
          print("Found end of section")
        return parsed_flags

      # We can get all sorts of text from the output. Including values that span multiple lines, etc.
      # We can only do a best-effort to recognise the things that look like flags and ignore the rest.
      match = _FLAG_LINE_REGEX.match(line)
      if match:
        namespace, key, value = match.groups()
        parsed_flags.append(
            {"namespace": namespace, "key": key, "value": value}
        )

  return parsed_flags


def handle_zip_file(file_path: str) -> list[dict]:
  """Handles the parsing of a zip file to extract flag values.

  It will try to find the main txt file that contains the bugreport logs and
  then process it to parse flags.
  """
  try:
    with zipfile.ZipFile(file_path, "r") as z:
      bugreport_entry = find_bugreport_inside_zip(z)
      if _verbose:
        print(f"handle_zip_file: {bugreport_entry=}")

      with z.open(bugreport_entry) as bugreport_file:
        # ignore errors as there are weird bytes in some files.
        contents = io.TextIOWrapper(bugreport_file, encoding="utf-8", errors="ignore")
        return parse_device_config_dumpsys(contents)
  except zipfile.BadZipFile:
    print(f"Error: {file_path} is not a valid zip file.", file=sys.stderr)
    sys.exit(1)


def find_bugreport_inside_zip(z: zipfile.ZipFile) -> str:
  """Tries to find the main txt file inside the zip that contains the logs.

  First it tries to find a file "main_entry.txt", read its contents which
  should be another filename, and then try to open that file.

  As a fallback, if "main_entry.txt" doesn't exist, it tries to open the
  first file with a name with the format "bugreport-*.txt".
  """
  if "main_entry.txt" in z.namelist():
    with z.open("main_entry.txt") as main_entry:
      return main_entry.read().decode("utf-8").strip()
  else:
    print(
        "The zipfile doesn't contain a main_entry.txt file. Attempting"
        " fallback.",
        file=sys.stderr,
    )
    for name in z.namelist():
      if name.startswith("bugreport-") and name.endswith(".txt"):
        return name
  print(
      "Could not find bugreport inside the zip file",
      file=sys.stderr
  )
  sys.exit(1)


def handle_txt_file(file_path: str) -> list[dict]:
  file_arg = sys.stdin.fileno() if file_path == "-" else file_path
  try:
    # ignore errors as there are weird bytes in some files.
    with open(file_arg, "r", encoding="utf-8", errors="ignore") as file:
      return parse_device_config_dumpsys(file)
  except FileNotFoundError:
    print(f"Error: File not found at {file_path}", file=sys.stderr)
    sys.exit(1)


def main():
  parser = argparse.ArgumentParser(
      description="Parse a DeviceConfig dumpsys file and extract flag information."
  )
  parser.add_argument(
      "file",
      help=(
          "Path to the file to analyse. Passing a zip file implies it is a "
          "bug report. Use '-' for stdin. Zip files over stdin are not supported."
      ),
  )
  parser.add_argument(
      "--verbose",
      action="store_true",
      help="Print more information",
  )
  args = parser.parse_args()

  global _verbose
  _verbose = args.verbose
  is_zip = args.file != "-" and zipfile.is_zipfile(args.file)
  if is_zip:
    # handle zip file
    flags = handle_zip_file(args.file)
  else:
    flags = handle_txt_file(args.file)

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
