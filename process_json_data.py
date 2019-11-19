#!/usr/bin/env python

import sys
import json
import os
from collections import defaultdict

# Same dir as this python file
data_base_dir = os.path.dirname(os.path.realpath(__file__))
data_base_path = data_base_dir + "/data.json"

def load(input_file):
    # read file
    with open(input_file, 'r') as json_file:
        data = json_file.read()

    # parse file
    obj = json.loads(data)
    mobo_serial = obj["Motherboard"]["Serial Number"]
    return mobo_serial, obj

def data_match(new_data, old_data, data_type):
    entries_to_compare = {"Motherboard": "Serial Number",
            "CPUs": "Version",
            "RAM": ["Serial Number", "Part Number"],
            "GPUs": "UUID",
            "HDDs": {"NVME":"SN", "HDD":"Serial Number"},
            "Monitors": "Serial Number"}

    keyword = entries_to_compare[data_type]

    if isinstance(keyword, list):
        for key in keyword:
            if new_data[key] != old_data[key]:
                return False
    elif isinstance(keyword, dict):
        new_key = keyword[new_data["Type"]]
        old_key = keyword[old_data["Type"]]
        if new_data[new_key] != old_data[old_key]:
            return False
    else:
        if new_data[keyword] != old_data[keyword]:
            return False

    return True

def process_new_computer_info(serial, new_data, old_data, used_dict, unused_dict):
    keywords = ["Motherboard", "CPUs", ["RAM", "Sticks"], "GPUs", "HDDs", "Monitors"]
    for keyword in keywords:
        if isinstance(keyword, list):
            new_key_data = new_data[keyword[0]]
            old_key_data = old_data[keyword[0]]
            for i in range(1,len(keyword)):
                new_key_data = new_key_data[keyword[i]]
                old_key_data = old_key_data[keyword[i]]
            #Set keyword for later usage
            keyword = keyword[0]
        else:
            new_key_data = new_data[keyword]
            old_key_data = old_data[keyword]

        if isinstance(new_key_data, list):
            for new_entry in new_key_data:
                found_match = False
                for old_entry in old_key_data:
                    if data_match(new_entry, old_entry, keyword):
                        found_match = True
                        old_key_data.remove(old_entry)
                        break
                if not found_match:
                    #Insert the serial of the computer in the new used entry
                    tmp = new_entry.copy()
                    tmp["Comp Serial"] = serial
                    used_dict[keyword].append(tmp)
            if len(old_data) != 0:
                for old_entry in old_key_data:
                    unused_dict[keyword].append(old_entry)
        else:
            #data is dict
            if not data_match(new_key_data, old_key_data, keyword):
               #Insert the serial of the computer in the new used entry
               tmp = new_key_data.copy()
               tmp["Comp Serial"] = serial
               used_dict[keyword].append(tmp)

               unused_dict[keyword].append(old_key_data)

#Main start

if len(sys.argv) < 2:
    print("You need to provide files to parse!")
    sys.exit()

if os.path.isfile(data_base_path):
    with open(data_base_path, 'r') as data_file:
        data = data_file.read()

    database = json.loads(data)
else:
    database = {"Computers": {}, "HW": {"used": {}, "unused": {}}}

data_to_add = []

# Default init all key values to lists
new_used_hw = defaultdict(list)
new_unused_hw = defaultdict(list)

for input_file in sys.argv[1:]:
    serial, data = load(input_file)

    if serial in database["Computers"]:
        process_new_computer_info(serial, data, database["Computers"][serial], new_used_hw, new_unused_hw)
        del database["Computers"][serial]
    else:
        #Add all hw to the used pile
        keywords = ["Motherboard", "CPUs", ["RAM", "Sticks"], "GPUs", "HDDs", "Monitors"]
        for keyword in keywords:
            if isinstance(keyword, list):
                new_key_data = data[keyword[0]]
                for i in range(1,len(keyword)):
                    new_key_data = new_key_data[keyword[i]]
                #Set keyword for later usage
                keyword = keyword[0]
            else:
                new_key_data = data[keyword]

            if isinstance(new_key_data, list):
                for new_entry in new_key_data:
                    #Insert the serial of the computer in the new used entry
                    tmp = new_entry.copy()
                    tmp["Comp Serial"] = serial
                    new_used_hw[keyword].append(tmp)
            else:
                #data is dict
                #Insert the serial of the computer in the new used entry
                tmp = new_key_data.copy()
                tmp["Comp Serial"] = serial
                new_used_hw[keyword].append(tmp)

    data_to_add.append({serial: data})

# Computers unaccounted for
if len(database["Computers"]):
    print("The following computers have not dumped their HW info for this update:")
    for comp in database["Computers"]:
        print("User: " + database["Computers"][comp]["User"])
        print("Serial: " + comp)
        print()

# Missing computers
missing_serials = [serial for serial in database["Computers"]]

print(missing_serials)

for data in data_to_add:
    # Add new computer
    for serial, comp_data in data.items():
        database["Computers"][serial] = comp_data

# Merge the unused HW list
for key, value in database["HW"]["unused"].items():
    new_unused_hw[key] += value

# Did any HW get reused?
for keyword in new_unused_hw:
    for entry in new_unused_hw[keyword]:
        for used in new_used_hw[keyword]:
            if data_match(used, entry, keyword):
                #This one was probably reused in a new computer
                new_unused_hw[keyword].remove(entry)
                break

# Merge the used HW list
for key, entry in database["HW"]["used"].items():
    new_used_hw[key] += entry

# Cleanup unused entries in the used/unused categories (warpped in list to be able to delete in the for loop)
for keyword in list(new_unused_hw):
    if len(new_unused_hw[keyword]) == 0:
        del new_unused_hw[keyword]

for keyword in list(new_used_hw):
    if len(new_used_hw[keyword]) == 0:
        del new_used_hw[keyword]

#Remove unused hw from the used dict. (and remove computer serial numbers from them)
for keyword in new_unused_hw:
    for entry in new_unused_hw[keyword]:
        if "Comp Serial" in entry:
            for used in new_used_hw[keyword]:
                if used["Comp Serial"] == entry["Comp Serial"] and data_match(used, entry, keyword):
                    new_used_hw[keyword].remove(used)
                    del entry["Comp Serial"]
                    break

database["HW"]["used"] = new_used_hw
database["HW"]["unused"] = new_unused_hw

with open(data_base_path, 'w') as data_file:
    json.dump(database, data_file)
