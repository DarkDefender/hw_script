#!/bin/bash

#sudo apt install lshw

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
echo ===\| General HW \|=== >> $file
printf '\n' >> $file

lshw -short >> $file

# lshw does not currently list the nvme drives, so dump the storage info with lsblk
printf '\n' >> $file
echo ===\| DISK LAYOUT \(and nvme info\)  \|=== >> $file
printf '\n' >> $file
lsblk -o NAME,FSTYPE,LABEL,MOUNTPOINT,SIZE,MODEL >> $file

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
