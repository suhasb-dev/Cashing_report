import orjson
import datetime
from collections import defaultdict

DATE_WISE_COUNTER = defaultdict(list)

with open("rep.json", "rb") as f:
    report = orjson.loads(f.read())

cache_read_status_list = report['report']['cache_read_status_none']["steps_list"]
max_date = max(cache_read_status_list, key=lambda x: datetime.datetime.fromisoformat(x['created_at']))
print(max_date["created_at"])

for step in cache_read_status_list:
    date = datetime.datetime.fromisoformat(step["created_at"]).date().strftime("%Y-%m-%d")
    DATE_WISE_COUNTER[date].append(step)

for date, count in DATE_WISE_COUNTER.items():
    print(f"{date}: {len(count)}")

with open("experiment.json", "wb") as f:
    f.write(orjson.dumps(DATE_WISE_COUNTER, option=orjson.OPT_INDENT_2))

cache_read_status_list = report['report']['no_cache_documents_found']["steps_list"]
# Command Wise Count
command_wise_counter = defaultdict(list)
for step in cache_read_status_list:
    command = step['command']
    command_wise_counter[command].append(step)

command_wise_counter_number = sorted([{"command": k, "count": len(v), "all_same": all(step.get("cache_doc_status", None) == 0 for step in v)} for k,v in command_wise_counter.items()], key=lambda x: x['count'], reverse=True)

import json
print(json.dumps(command_wise_counter_number, indent=4))


print("####################################################################")
not_cache_count = 0
total_count = 0
for command, list_of_steps in command_wise_counter.items():
    if len(list_of_steps)!=1 and all(step.get("cache_doc_status", None) == 0 for step in list_of_steps):
        print(f"[NEVER CACHED] {command}")
        not_cache_count += len(list_of_steps)
    total_count += len(list_of_steps)

print(f"Total Never Cached: {not_cache_count}")
print(f"Total Cached: {total_count - not_cache_count}")

with open("no_cache_document_found_command_wise_counter.json", "wb") as f:
    f.write(orjson.dumps(command_wise_counter, option=orjson.OPT_INDENT_2))