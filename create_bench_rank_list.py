#!/usr/bin/env python
import sys
import json
import re
from operator import attrgetter, itemgetter

if len(sys.argv) < 3:
    print("You need to provide a file to parse and an output file!")
    sys.exit()

out_file = sys.argv[-1]

with open("./bench_data/cpus.json", "r") as read_file:
    data_cpu = json.load(read_file)

with open("./bench_data/cuda.json", "r") as read_file:
    data_gpu = json.load(read_file)

cpu_bench_data = data_cpu["body"]
gpu_bench_data = data_gpu["body"]

comp_list = []

for input_file in sys.argv[1:-1]:
    print(input_file)
    with open(input_file, "r") as read_file:
        input_data = json.load(read_file)

    comp_list.append(input_data)

    file_name = input_file.split("/")[-1].split(".")[0]
    input_data["file_name"] = file_name

    #Get the average score

    cpu_str = input_data["CPUs"][0]["Version"]
    cpu_nr = len(input_data["CPUs"])

    #Strip parentheses from CPU string, otherwise Intel CPUs won't match with the benchmark strings.
    cpu_str = re.sub(r'\([^)]*\)', '', cpu_str)

    cpu_result = []

    for cpu_data in cpu_bench_data:
        if cpu_str in cpu_data[0]:
            cpu_result = cpu_data

    if len(cpu_result) == 0:
        cpu_result = "N/A"
    else:
        cpu_result = cpu_result[1] / cpu_nr

    input_data["CPU score"] = cpu_result

    if not "NVIDIA" in input_data["GPUs"][0]["Vendor"]:
        gpu_result = "N/A"
        input_data["GPU score"] = gpu_result
        continue

    gpu_str = input_data["GPUs"][0]["Model"]
    gpu_nr = len(input_data["GPUs"])

    gpu_result = []

    for gpu_data in gpu_bench_data:
        if gpu_str in gpu_data[0]:
            gpu_result = gpu_data

    if len(gpu_result) == 0:
        gpu_result = "N/A"
    else:
        gpu_result = gpu_result[1]

    input_data["GPU score"] = gpu_result
    print(gpu_result)

#print(str(comp_list))
comp_list = sorted(comp_list, key=itemgetter('CPU score'))

out = open(out_file,"w")

for comp in comp_list:
    out.write("file_name: ")
    out.write(comp["file_name"])
    out.write("\n")

    out.write("CPU score: ")
    out.write(str(comp["CPU score"]))
    out.write("\n")

    out.write("GPU score: ")
    out.write(str(comp["GPU score"]))
    out.write("\n")

    out.write("CPUs:\n")
    for cpu in comp["CPUs"]:
        out.write("\t")
        out.write(cpu["Version"])
        out.write("\n")

    out.write("RAM: ")
    out.write(str(comp["RAM"]["Total RAM (GB)"]))
    out.write(" GB\n")

    out.write("GPUs:\n")
    for gpu in comp["GPUs"]:
        out.write("\t")
        out.write(gpu["Model"])
        out.write("\n")

    out.write("\n")

out.close()
