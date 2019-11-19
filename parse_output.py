#!/usr/bin/env python

import json
import sys
import os
import re
import math

def os_parse(f, output_data):
    f.readline() #Skip blank line
    output_data["OS"] = f.readline()[:-1] #skip newline

def mobo_parse(f, output_data):
    #Skip the first line
    f.readline()

    mobo_data = dict()

    prev_line_empty = False

    section_type = -1
    sec2_keys = ["Manufacturer:", "Product Name:", "Serial Number:"]

    while True:
        out = f.readline()
        if len(out.split()) == 0:
            section_type = -1
            if prev_line_empty:
                #End of MOBO section
                break
            prev_line_empty = True
        elif section_type == 2:
            if any(keyword in out for keyword in sec2_keys):
                out = out.split(":")
                mobo_data[out[0].strip()] = out[1].strip()
        else:
            prev_line_empty = False
            if "DMI type 2" in out:
                section_type = 2

    output_data["Motherboard"] = mobo_data

def cpu_parse(f, output_data):
    #Skip the first line
    f.readline()

    cpus = list()
    cpu_data = dict()

    prev_line_empty = False

    cpu_keys = ["Socket Designation:", "Type:", "Manufacturer:", "ID:", "Version:", "Current Speed:", "Thread Count:", "Upgrade:"]

    while True:
        out = f.readline()
        if len(out.split()) == 0:
            if prev_line_empty:
                #End of CPU section
                break
            prev_line_empty = True
            if len(cpu_data) != 0:
                cpus.append(cpu_data)
                cpu_data = dict()
        elif any(keyword in out for keyword in cpu_keys):
            prev_line_empty = False
            out = out.split(":")
            cpu_data[out[0].strip()] = out[1].strip()

    output_data["CPUs"] = cpus

def ram_parse(f, output_data):
    #Skip the first line
    f.readline()

    ram_data = dict()
    ram_stick = dict()
    ram_sticks = list()

    total_mem = 0

    prev_line_empty = False

    section_type = -1
    sec16_keys = ["Maximum Capacity:", "Number Of Devices:"]
    sec17_keys = ["Size:", "Manufacturer:", "Serial Number:", "Part Number:", "Configured Memory Speed:", "Type:"]

    while True:
        out = f.readline()
        if len(out.split()) == 0:
            section_type = -1
            if prev_line_empty:
                #End of RAM section
                break
            prev_line_empty = True
            if len(ram_stick) != 0:
                ram_sticks.append(ram_stick)
                ram_stick = dict()
        elif section_type == 16:
            if any(keyword in out for keyword in sec16_keys):
                out = out.split(":")
                label = out[0].strip()
                if label in ram_data:
                    #Add the quantities together
                    old_data = int(ram_data[label].split()[0])
                    new_data = out[1].split()
                    new_data[0] = str( int(new_data[0]) + old_data )

                    new_data = " ".join(new_data)
                    ram_data[label] = new_data
                else:
                    ram_data[label] = out[1].strip()
        elif section_type == 17:
            if any(keyword in out for keyword in sec17_keys):
                out = out.split(":")
                ram_stick[out[0].strip()] = out[1].strip()
                if out[0].strip() == "Size":
                    mem = out[1].split()[0]
                    if not mem.isdigit():
                        #This slot is not populated
                        section_type = -1
                        ram_stick.clear()
                        continue
                    total_mem = total_mem + int(mem)
        else:
            prev_line_empty = False
            if "DMI type 16" in out:
                section_type = 16
            elif "DMI type 17" in out:
                section_type = 17

    ram_data["Total RAM (GB)"] = total_mem / 1024
    ram_data["Sticks"] = ram_sticks
    output_data["RAM"] = ram_data

def gpu_parse(f, output_data):
    #Skip the first line
    f.readline()

    gpus = list()
    info = dict()

    while True:
        out = f.readline()
        if len(out.split()) == 0:
            #End of GPU section
            break
        elif out[0:3] == "---":
            if "UUID" in info:
                #Only save GPUs with UUIDs
                gpus.append(info)
            info = dict()
        else:
            data = out.split(":")

            if data[0] == "GPU UUID":
                #Nvidia cards
                data[0] = "UUID"

            if len(data) == 2:
                info[data[0]] = data[1].strip()
            else:
                #we need to stitch together the data string again
                info[data[0]] = ":".join(data[1:]).strip()

    output_data["GPUs"] = gpus

def disk_parse(f, output_data):
    #Skip the first line
    f.readline()

    has_drive = False
    drives = list()
    info = dict()
    info["Type"] = "HDD"

    #HDDs
    while True:
        out = f.readline()
        if len(out.split()) == 0:
            #End of HDD section
            if has_drive:
                drives.append(info)
            break
        if out[0] == "/":
            if has_drive:
                drives.append(info)
                info = dict()
                info["Type"] = "HDD"
            info["Node"] = out.strip()
            has_drive = True
        else:
            data = out.split(":")
            if data[0] == "device size with M = 1000*1000":
                #Check if this is a empty disk (probably disconnected)
                data_size = int(data[1].split()[0])
                if data_size == 0:
                    #Throw away the data
                    has_drive = False
                    info = dict()
                    info["Type"] = "HDD"

            info[data[0].strip()] = data[1].strip()

    output_data["HDDs"] = drives

def nvme_parse(f, output_data):
    #Skip the first line
    f.readline()

    nvme_drives = list()

    category = f.readline().split()

    category_range = list()
    range_start = 0
    range_end = 0
    for entry in f.readline().split():
        range_end = range_end + len(entry) +1
        category_range.append(slice(range_start, range_end))
        range_start = range_end

    #HDDs
    while True:
        out = f.readline()
        if len(out.split()) == 0:
            #End of NVME section
            break
        else:
            info = dict()
            info["Type"] = "NVME"
            for idx, r in enumerate(category_range):
                info[category[idx]] = out[r].strip()
            nvme_drives.append(info)

    output_data["HDDs"] += nvme_drives

def input_parse(f, output_data):
    #Skip the first line
    f.readline()

    input_list = list()

    found_devs = dict() #vendor id : product list

    prev_line_empty = False
    in_section = False

    vendor_black_list = ["0000"]

    while True:
        out = f.readline()
        if len(out.split()) == 0:
            if prev_line_empty:
                #End of input section
                break
            prev_line_empty = True
            in_section = False
        elif out[0] == "I":
            prev_line_empty = False
            vendor = out.split()[2].split("=")[1]
            product = out.split()[3].split("=")[1]
            if vendor in vendor_black_list:
                continue
            elif vendor in found_devs and found_devs[vendor] == product:
                continue
            found_devs[vendor] = product
            in_section = True
        elif in_section and out[0] == "N":
            out = out[3:].split("=")
            out = out[1].strip().strip('"')
            input_list.append(out)

    output_data["Input devices"] = input_list

def monitor_parse(f, output_data):
    in_section = False
    mon_info_list = list()
    mon_info = dict()
    native_mode = '"Mode 0"' #The native resolution monitor mode
    modes = list()
    for line in f:
        out = line.split()
        if len(out) == 0:
            continue

        if out[0] == "Section":
            in_section = True
            continue
        if out[0] == "EndSection":
            str_len = len(native_mode)

            if str_len == 0:
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
                if fallback_mode or native_mode == mode[:str_len]:
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

        if not in_section:
            #The card and output port
            mon_info["Connector"] = out[0]
        else:
            if out[0] == "ModelName":
                mon_info["Model"] = " ".join(out[1:]).strip('"')
            elif out[0] == "VendorName":
                mon_info["Vendor"] = " ".join(out[1:]).strip('"')
            elif out[0] == "Modeline":
                modes.append( " ".join(out[1:]) )
            elif out[0] == "Option" and out[1] == '"PreferredMode"':
                native_mode = " ".join(out[2:])
            elif out[0] == "VertRefresh":
                mon_info["Refresh Rate"] = out[1]
            elif out[0] == "DisplaySize":
                v_size = int(out[1])
                h_size = int(out[2])
                inch = math.sqrt(v_size ** 2 + h_size ** 2) / 25.4
                mon_info["Display Dimentions (mm)"] = [v_size, h_size]
                mon_info["Display Size (inch)"] = inch
            elif "Monitor Manufactured" in line:
                mon_info["Manufacture date"] = line[24:-1]
            elif "Serial Number" in line:
                mon_info["Serial Number"] = line[17:-1].strip('"')

    if in_section:
        #Something is wrong, this shouldn't happen
        output_data["Monitors"] = "Error parsing monitor data, check input file"
    else:
        output_data["Monitors"] = mon_info_list

#Main section start

if len(sys.argv) < 3:
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
        if len(line_parse) != 3:
            #Not a section line
            continue

        line_parse = line_parse[1]
        if line_parse == " OS ":
            #===| OS |===
            os_parse(f, output_data)
        elif line_parse == " Motherboard ":
            #===| Motherboard |===
            mobo_parse(f, output_data)
        elif line_parse == " CPU ":
            #===| CPU |===
            cpu_parse(f, output_data)
        elif line_parse == " RAM ":
            #===| RAM |===
            ram_parse(f, output_data)
        elif line_parse == " GPU ":
            #===| GPU |===
            gpu_parse(f, output_data)
        elif line_parse == " HDD ":
            #===| HDD |===
            disk_parse(f, output_data)
        elif line_parse == " NVME ":
            #===| NVME |===
            nvme_parse(f, output_data)
        elif line_parse == " Input devices ":
            #===| Input devices |===
            input_parse(f, output_data)
        elif line_parse == " Monitor info ":
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
