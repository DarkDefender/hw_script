#!/bin/bash

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

cd $DIR

if [[ $EUID -ne 0 ]]; then
  #hw_script.sh requires root.
  echo "This script must be run as root (sudo)."
  exit 1
fi

while true; do
  # Ask the user for their name
  echo "What is your unique blender studio name? (Or unique name for the computer you are at)" 
  read var_name

  [ ! -f "hw_data/$var_name" ] && break
  echo There is already an output file with that name!
  read -p "Do you want to overwrite it (y/n)? " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    exit 1
  else
    break
  fi
done

# Does the output directory exist?
# If not, create it!
[ ! -d "hw_data" ] && mkdir hw_data

./hw_script.sh hw_data/$var_name
