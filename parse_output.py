#!/usr/bin/env python

import json
import sys
import os
import math

brief_output = False

def os_parse(f, output_data):
    f.readline() #Skip blank line
    output_data["OS"] = f.readline()[:-1] #skip newline

def net_parse(f, output_data):
    f.readline() #Skip blank line

    net_ifaces = list()
    net_data = dict()

    prev_line_empty = False
    entry = 0

    net_entries = ["Interface", "MAC", "IP", "PCI address", "Type", "Manufacturer", "Product Name"]
    brief_entries = [1,2]

    while True:
        out = f.readline()
        if len(out.split()) == 0:
            section_type = -1
            if prev_line_empty:
                #End of net section
                break
            net_ifaces.append(net_data)
            net_data = dict()

            prev_line_empty = True
            entry = 0
        else:
            prev_line_empty = False
            if brief_output and entry not in brief_entries:
                entry += 1
                continue
            if len(net_entries) <= entry:
                continue
            # Add entry to dict
            net_data[net_entries[entry]] = out.strip()
            entry += 1

    output_data["Network"] = net_ifaces

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

    if brief_output:
        cpu_keys = ["Version:"]
    else:
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
                    unit_size = out[1].split()[1]
                    #Convert to GB
                    if (unit_size == "MB"):
                        mem = int(mem) / 1024
                    elif (unit_size == "TB"):
                        mem = int(mem) * 1024
                    else:
                        mem = int(mem)

                    total_mem = total_mem + mem
        else:
            prev_line_empty = False
            if "DMI type 16" in out:
                section_type = 16
            elif "DMI type 17" in out:
                section_type = 17

    if brief_output:
        ram_data.clear()
    else:
        ram_data["Sticks"] = ram_sticks

    ram_data["Total RAM (GB)"] = total_mem
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
            if "NVIDIA" in info["Vendor"] or "AMD" in info["Vendor"]:
               #Only save GPUs from Nvidia and AMD
                if brief_output:
                    new_info = dict()
                    new_info["Vendor"] = info["Vendor"]
                    new_info["Model"] = info["Model"]
                    info = new_info
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

    for line in f:
        out = line.strip()
        if len(out) == 0:
            continue

        out = out.split(":")

        if out[0] == "Section":
            in_section = True
            continue
        if out[0] == "EndSection":
            if brief_output:
                mon_info_new = dict()
                mon_info_new["Display Size (inch)"] = mon_info["Display Size (inch)"]
                mon_info = mon_info_new

            in_section = False
            mon_info_list.append(mon_info)
            mon_info = dict()
            continue

        if not in_section:
            #The card and output port
            mon_info["Connector"] = out[0]
        else:
            if out[0] == "Display Product Name":
                mon_info["Model"] = out[1][1:].strip("'")
            elif out[0] == "Manufacturer":
                mon_info["Vendor"] = out[1][1:]
            elif out[0] == "Native Video Resolution":
                mon_info["Native Resolution"] = out[1][1:]
            elif out[0] == "Monitor ranges (Bare Limits)":
                mon_info["Refresh Rate"] = out[1].split()[0] + " Hz"
            elif out[0] == "Maximum image size":
                # Assuming that this is always in centimeters
                temp = out[1].split("x")
                v_size = int(temp[0].split()[0])
                h_size = int(temp[1].split()[0])
                inch = math.sqrt(v_size ** 2 + h_size ** 2) / 2.54
                mon_info["Display Dimentions (cm)"] = [v_size, h_size]
                mon_info["Display Size (inch)"] = inch
            elif out[0] == "Made in":
                mon_info["Manufacture date"] = out[1][1:]
            elif out[0] == "Display Product Serial Number":
                mon_info["Serial Number"] = out[1][1:].strip("'")
            elif out[0] == "Bits per primary color channel":
                mon_info["Color depth"] = out[1][1:]
            elif out[0] == "Supported color formats":
                out = line[25:].strip()
                mon_info["Color formats"] = out.split(", ")

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
        continue
        #sys.exit()

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
            if brief_output:
                continue
            os_parse(f, output_data)
        elif line_parse == " Network ":
            net_parse(f, output_data)
        elif line_parse == " Motherboard ":
            #===| Motherboard |===
            if brief_output:
                continue
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
            if brief_output:
                continue
            disk_parse(f, output_data)
        elif line_parse == " NVME ":
            #===| NVME |===
            if brief_output:
                continue
            nvme_parse(f, output_data)
        elif line_parse == " Input devices ":
            #===| Input devices |===
            if brief_output:
                continue
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
        f_out = open(out_dir + filename + ".json","w")
    except:
        print("Couldn't open file " + input_file + " for writing")
        sys.exit()
    f_out.write(out_json)
