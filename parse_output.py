#!/usr/bin/env python

import json
import sys
import os
import re

def get_section_range(string):
    space_num = 0
    prev_end = 0
    section = 0
    ranges = list()

    for pos, char in enumerate(string):
        if (char == " "):
            space_num += 1
            if (space_num == 1 and string[pos+1] != " "):
                space_num = 0
        elif (space_num > 0):
            ranges.append(slice(prev_end, pos))
            prev_end = pos
            space_num = 0
            section += 1

        if (pos + 1 == len(string)):
            ranges.append(slice(prev_end, -1))

    return ranges

def os_parse(f, output_data):
    f.readline() #Skip blank line
    output_data["OS"] = f.readline()[:-1] #skip newline

def hw_parse(f, output_data):
    #Get the section info
    f.readline()
    sec_range = get_section_range(f.readline())
    f.readline()

    #Onto the actuall HW data
    ram_sticks = list()
    cpus = list()
    gpus = list()
    hdds = list()
    input_dev = list()

    while True:
        data = f.readline()
        if (len(data) <= 1):
            #We have reached the end of the HW section
            break

        sections = list()
        for r in sec_range:
            sections.append(data[r].strip())

        if (sections[0] == "/0"):
            #Get to the motherboard name
            output_data["Motherboard"] = sections[-1]
        elif (sections[2] == "processor"):
            info = dict()
            info["Vendor"] = sections[-1].split()[0]
            info["Model"] = sections[-1]
            cpus.append( info )
        elif (sections[2] == "memory" and "DIMM" in sections[-1]):
            #Get the Ram info
            if(sections[3][0].isdigit()):
                #Populated RAM slot!
                ram_sticks.append( sections[-1] )
        elif (sections[2] == "display"):
            #GPU info
            info = dict()
            name = sections[-1]
            if (name == "NVIDIA Corporation"):
                #Because of too new card or experimental drivers?
                info["Vendor"] = "NVIDIA"
                info["Model"] = "(Unknown model, need manual check)"
                gpus.append(info)
                continue

            info["Model"] = name

            if ("Radeon" in name):
                info["Vendor"] = "AMD"
            elif ("GeForce" in name or "Quadro" in name or "TITAN" in name):
                info["Vendor"] = "Nvidia"
            else:
                info["Vendor"] = "Unknown"

            gpus.append(info)
        elif (sections[2] == "disk"):
            disk_data = sections[-1].split()
            if (len(disk_data) == 0):
                continue
            info = dict()
            if (disk_data[0][0].isdigit()):
                info["Type"] = "HDD"
                info["Size"] = disk_data[0]
            else:
                info["Type"] = disk_data[0]
            info["Vendor"] = disk_data[1].split("_")[0] #some disk strings has underscores
            info["Model"] = " ".join(disk_data[1:])
            hdds.append(info)
        elif (sections[2] == "input"):
            input_dev.append(sections[-1])

    #Some extra processing on ram
    total_mem = 0
    for stick in ram_sticks:
        #Assuming GiB for now
        total_mem += int(re.search(r'\d+', stick.split()[0]).group())
    output_data["RAM"] = {"Total RAM" : total_mem, "Sticks" : ram_sticks}

    output_data["CPUs"] = cpus
    output_data["GPUs"] = gpus
    output_data["HDDs"] = hdds
    output_data["Input devices"] = input_dev

def disk_parse(f, output_data):
    #Skip the first two lines
    f.readline()
    f.readline()

    nvme_drives = list()

    while True:
        out = f.readline().split()
        if (len(out) == 0):
            #End of section
            break
        if (out[0][0:4] == "nvme"):
            info = dict()
            info["Type"] = "nvme"
            info["Size"] = out[1]+"B"
            info["Vendor"] = out[2]
            info["Model"] = " ".join(out[2:])
            nvme_drives.append(info)

    output_data["HDDs"] += nvme_drives

def monitor_parse(f, output_data):
    in_section = False
    mon_info_list = list()
    mon_info = dict()
    native_mode = '"Mode 0"' #The native resolution monitor mode
    modes = list()
    for line in f:
        out = line.split()
        if (len(out) == 0):
            continue

        if (out[0] == "Section"):
            in_section = True
            continue
        if (out[0] == "EndSection"):
            str_len = len(native_mode)

            if (str_len == 0):
                #Just pick the first mode
                res_data = modes[0][8:].split()
                try:
                    mon_info["Native Resolution"] = res_data[1] + "x" + res_data[5]
                except:
                    pass
                in_section = False
                mon_info_list.append(mon_info)
                mon_info = dict()
                modes = list()
                native_mode = ""
                continue

            #Workaround for crappy displays that lists modes without any info
            fallback_mode = False #Try to fallback to the first valid mode
            for mode in modes:
                if (fallback_mode or native_mode == mode[:str_len]):
                    res_data = mode[str_len:].split()
                    try:
                        mon_info["Native Resolution"] = res_data[1] + "x" + res_data[5]
                    except:
                        fallback_mode = True
                        str_len = 8
                    else:
                        break

            in_section = False
            mon_info_list.append(mon_info)
            mon_info = dict()
            modes = list()
            native_mode = ""
            continue

        if (not in_section):
            #The card and output port
            mon_info["Connector"] = out[0]
        else:
            if (out[0] == "ModelName"):
                mon_info["Model"] = " ".join(out[1:]).strip('"')
            elif (out[0] == "VendorName"):
                mon_info["Vendor"] = " ".join(out[1:]).strip('"')
            elif (out[0] == "Modeline"):
                modes.append( " ".join(out[1:]) )
            elif (out[0] == "Option" and out[1] == '"PreferredMode"'):
                native_mode = " ".join(out[2:])
            elif (out[0] == "VertRefresh"):
                mon_info["Refresh Rate"] = out[1]
            elif ("Monitor Manufactured" in line):
                mon_info["Manufacture date"] = line[24:-1]

    if (in_section):
        #Something is wrong, this shouldn't happen
        output_data["Monitors"] = "Error parsing monitor data, check input file"
    else:
        output_data["Monitors"] = mon_info_list

#Main section start

if (len(sys.argv) < 3):
    print("You need to provide a file to parse and output directory!")
    sys.exit()

out_dir = sys.argv[-1]

for input_file in sys.argv[1:-1]:
    print(input_file)
    try:
        f= open(input_file,"r")
    except:
        print("Couldn't open file " + input_file + " for reading")
        sys.exit()

    output_data = dict()

    filename = os.path.basename(input_file)

    output_data["User"] = filename
    output_data["Hostname"] = f.readline()[:-1] #skip newline

    for line in f:
        line_parse = line.split("|")
        if (len(line_parse) != 3):
            #Not a section line
            continue

        line_parse = line_parse[1][1]
        if (line_parse == "O"):
            #===| OS |===
            os_parse(f, output_data)
        elif (line_parse == "G"):
            #===| General HW |===
            hw_parse(f, output_data)
        elif (line_parse == "D"):
            #===| DISK LAYOUT (and nvme info) |===
            disk_parse(f, output_data)
        elif (line_parse == "M"):
            #===| Monitor info |===
            monitor_parse(f, output_data)
        else:
            print("Unknown section value! Exiting...")
            sys.exit()

    #convert to json
    out_json = json.dumps(output_data)
    try:
        f_out = open(out_dir + filename + ".json","w+")
    except:
        print("Couldn't open file " + input_file + " for writing")
        sys.exit()
    f_out.write(out_json)
