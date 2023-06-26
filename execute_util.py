import random
import settings_refuel as s

def form_activity_list(row) -> list:
    activity_list = []
    for activity in s.ACTIVITY_LIST:
        if row[activity] != 'DONE':
            activity_list.append(activity)
    return activity_list

def generate_activity(row) -> str:
    activity_list = form_activity_list(row)
    if len(activity_list) != 0:
        return random.choice(activity_list)
    else:
        return s.NO_ACTIVITY