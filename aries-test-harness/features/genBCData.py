#!/usr/bin/python

import csv
import os.path
import sys
import urllib.request


def download_sheet():
    long_id = "1r40t6TRAoMrmDO7vM_o6eOmk6jvxUr189wZVNBcdgVs"
    gid = "402169133"

    csv_url = f"https://docs.google.com/spreadsheets/d/{long_id}/export?gid={gid}&format=csv&id={long_id}"
    xlsx_url = f"https://docs.google.com/spreadsheets/d/{long_id}/export?format=xlsx&id={long_id}"

    urllib.request.urlretrieve(xlsx_url, "./Mapping Aries Protocols for Testing - Aries Agent Test Scripts.xlsx")
    urllib.request.urlretrieve(csv_url, "./Mapping Aries Protocols for Testing - Aries Agent Test Scripts.csv")

# If filename provided use that
if (len(sys.argv) - 1 >= 1):
    if not os.path.isfile(sys.argv[1]):
        print("Error: Input file name does not exist. Google Sheet must be provided as a parameter and exist.")
        exit(1)

    input = sys.argv[1]
# Else download the public sheet
else:
    download_sheet()
    input = "./Mapping Aries Protocols for Testing - Aries Agent Test Scripts.csv"


rfc = None
command_rows = {}
fieldnames = None

with open(input, "r") as proto_file:
    proto_reader = csv.DictReader(proto_file)
    for row in proto_reader:
        if row["RFC"] and 0 < len(row["RFC"]):
            rfc = row["RFC"]
        if (row["Command"] and 0 < len(row["Command"])) or (row["Response"] and 0 < len(row["Response"])):
            new_row = {
                "rfc": rfc,
                "command": row["Command"],
                "response": row["Response"],
                "topic": row["Topic"],
                "method": row["Method"],
                "operation": row["Operation"],
                "id": "Y" if row["Id"] and 0 < len(row["Id"]) else "",
                "data": "Y" if row["Data Parameter"] and 0 < len(row["Data Parameter"]) else "",
                "description": row["Description"],
                "id_details": row["Id"],
                "data_details": row["Data Parameter"],
                "result_details": row["Result"],
            }
            if not fieldnames:
                fieldnames = new_row.keys()
            row_key = (new_row["command"] + "_" +
                       new_row["response"] + "_" +
                       new_row["method"] + "_" +
                       new_row["topic"] + "_" +
                       new_row["method"] + "_" +
                       new_row["operation"] + "_" +
                       new_row["id"] + "_" +
                       new_row["data"])
            old_row = command_rows[row_key] if row_key in command_rows else {}
            for key, val in new_row.items():
                if (key not in old_row or not old_row[key] or 0 == len(old_row[key])):
                    old_row[key] = new_row[key]
            command_rows[row_key] = old_row

with open('../../aries-backchannels/data/backchannel_operations.csv', 'w') as command_file:
    writer = csv.DictWriter(command_file, fieldnames=fieldnames)
    writer.writeheader()
    for key, val in command_rows.items():
        writer.writerow(val)
