#!/bin/bash

#sudo apt install dmidecode hdparm nvme-cli

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
    #AMD/Intel
    echo Model: ${gpu_data[2]} >> $file
    uuid=$(cat /sys/bus/pci/devices/0000\:$pcibus/unique_id)
    echo UUID: $uuid >> $file
  fi

  echo "---" >> $file
done <<< "$gpu_cmd"

printf '\n' >> $file
echo ===\| HDD \|=== >> $file
printf '\n' >> $file

if [ -f /dev/sda ]; then
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

# Are we on a computer with closed source nvidia drivers?
# Not fail safe, but should be good enough of a check
if [ -x "$(command -v nvidia-settings)" ]
then
  #Split out edid info from xrandr
  cd /tmp/
  xrandr --listmonitors --verbose | awk '/EDID/{x="F"++i;}{print > /tmp/x;}'
  cd -

  for edid_file in /tmp/0F*
  do
    sed -n -i'' '/EDID:/,/BorderDimensions:/{//!p}' $edid_file
    tr -d "[:space:]" < $edid_file > /tmp/tmp_data
    xxd -r -p /tmp/tmp_data $edid_file
    ./parse-edid < $edid_file >> $file
  done

  exit 0
fi

MONITOR_OUTPUTS=/sys/class/drm/card*-*
for output in $MONITOR_OUTPUTS
do
  #Is there something connected to this output?
  if grep -Fxq "connected" $output/status
  then
    #Print the card and output port
    basename $output >> $file
    printf '\n' >> $file
    #Print the monitor info
    ./parse-edid < $output/edid >> $file
    printf '\n' >> $file
  fi
done
