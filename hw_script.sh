#!/bin/bash

# We require root to extract certain information.
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

#Check if the required commands exist

missing_command=false

command -v dmidecode >/dev/null 2>&1 || { echo >&2 "I require 'dmidecode' but it's not installed.  Aborting."; missing_command=true; }
command -v hdparm >/dev/null 2>&1 || { echo >&2 "I require 'hdparm' but it's not installed.  Aborting."; missing_command=true; }
command -v nvme >/dev/null 2>&1 || { echo >&2 "I require 'nvme-cli' but it's not installed.  Aborting."; missing_command=true; }
command -v edid-decode >/dev/null 2>&1 || { echo >&2 "I require 'edid-decode' but it's not installed.  Aborting."; missing_command=true; }

if [ "$missing_command" = true ] ; then
  exit 1
fi

# read-edid is supplied in this script directory
cd `dirname "$BASH_SOURCE"`

#Exit script if any command fails
set -e

file=$1
if [ -z "$1" ]
then
  echo "You need to specify filepath for the output!"
  exit 1
fi

comp_name=$(hostname)
#Make sure that our file is clear (no appending!)
echo -n $comp_name > $file
#Check if we supplied any more ID data
if [ ! -z "$2" ]
then
  echo " ($2)" >> $file
fi

printf '\n' >> $file
echo ===\| OS \|=== >> $file
printf '\n' >> $file

#Source the os release file
. /etc/os-release
echo $PRETTY_NAME >> $file

printf '\n' >> $file
echo ===\| Network \|=== >> $file
printf '\n' >> $file

for iface in /sys/class/net/*
do
  if [ -f "$iface/device/uevent" ]; then
    # This is a non virtual device, save information about it
    echo ${iface##*/} >> $file
    # Get mac adress
    cat "$iface/address" >> $file
    # Get ip adress
    if grep -q up "$iface/operstate"; then
      ifconfig ${iface##*/} | grep "inet " | awk '{print $2}' >> $file
    else
      echo DOWN >> $file
    fi
    # Get the device pci bus address
    pci_addr=$(cat "$iface/device/uevent" | grep -Po 'PCI_SLOT_NAME=\K.*')
    # Dump device model name and extra info
    lspci -mm -s $pci_addr | xargs -n 1 printf "%s\n" >> $file
    printf '\n' >> $file
  fi
done

printf '\n' >> $file
echo ===\| Motherboard \|=== >> $file
printf '\n' >> $file

dmidecode --type baseboard | tail -n +5 >> $file

printf '\n' >> $file
echo ===\| CPU \|=== >> $file
printf '\n' >> $file

dmidecode --type processor | tail -n +5 >> $file

printf '\n' >> $file
echo ===\| RAM \|=== >> $file
printf '\n' >> $file

dmidecode --type memory | tail -n +5 >> $file

printf '\n' >> $file
echo ===\| GPU \|=== >> $file
printf '\n' >> $file


#Taken from neofetch
gpu_cmd="$(lspci -mm | awk -F '\"|\" \"|\\(' \
                                          '/"Display|"3D|"VGA/ {a[$0] = $1 " | " $3 " | " $4}
                                           END {for(i in a) {if(!seen[a[i]]++) print a[i]}}')"

nr_of_gpus=0

while IFS= read -r gpu
do
  ((nr_of_gpus=nr_of_gpus+1))
  IFS='|' read -ra gpu_data <<< "$gpu"

  #Trim whitespace on pcibus
  pcibus=$(echo ${gpu_data[0]} | xargs)

  echo On pci bus: $pcibus >> $file
  echo Vendor: ${gpu_data[1]} >> $file

  if [[ ${gpu_data[1]} == *"NVIDIA"* ]]; then
    #Nvidia cards
    cat /proc/driver/nvidia/gpus/0000\:$pcibus/information | grep 'Model:\|UUID:' >> $file
  else
    #Other
    echo Model: ${gpu_data[2]} >> $file

    uuid_file=/sys/bus/pci/devices/0000\:$pcibus/unique_id

    if [ -e $uuid_file ]; then
      uuid=$(cat $uuid_file)
      echo UUID: $uuid >> $file
    fi
  fi

  echo "---" >> $file
done <<< "$gpu_cmd"

printf '\n' >> $file
echo ===\| HDD \|=== >> $file
printf '\n' >> $file

if [ -b /dev/sda ]; then
  for hdd in /dev/sd*[a-z]
  do
    echo $hdd >> $file
    hdparm -I $hdd | grep 'Model Number:\|Serial Number:\|Firmware Revision:\|device size with M = 1000\*1000:\|Form Factor:\|Nominal Media Rotation Rate:' >> $file
  done
fi

printf '\n' >> $file
echo ===\| NVME \|=== >> $file
printf '\n' >> $file

nvme list >> $file

printf '\n' >> $file
echo ===\| Input devices \|=== >> $file
printf '\n' >> $file

cat /proc/bus/input/devices >> $file

printf '\n' >> $file
echo ===\| Monitor info \|=== >> $file
printf '\n' >> $file

MONITOR_OUTPUTS=/sys/class/drm/card*-*
for output in $MONITOR_OUTPUTS
do
  #Is there something connected to this output?
  if grep -Fxq "connected" $output/status
  then
    #Print the card and output port
    basename $output >> $file
    printf '\n' >> $file
    #Print relevant monitor info
    # awk '{$1=$1};1' trims whitespace in the output
    edid_output=$(edid-decode -sn $output/edid | awk '{$1=$1};1')

    echo Section >> $file
    # Both name and serial number
    echo "$edid_output" | grep "Display Product" >> $file
    echo "$edid_output" | grep "Manufacturer" >> $file
    # Manufacturing date
    echo "$edid_output" | grep "Made in" >> $file
    echo "$edid_output" | grep "Maximum image size" >> $file
    echo "$edid_output" | grep "Bits per primary color channel" >> $file
    echo "$edid_output" | grep "Supported color formats" >> $file
    echo "$edid_output" | grep "Monitor ranges" >> $file
    # Native resolution
    echo Native Video Resolution: $(echo "$edid_output" | tail -n1) >> $file
    echo EndSection >> $file
    printf '\n' >> $file
  fi
done
