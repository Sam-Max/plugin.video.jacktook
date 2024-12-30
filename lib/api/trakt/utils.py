from datetime import datetime
import random
import re
import time



def jsondate_to_datetime(jsondate_object, resformat, remove_time=False):
    if not jsondate_object:
        return None
    if remove_time:
        datetime_object = datetime_workaround(jsondate_object, resformat).date()
    else:
        datetime_object = datetime_workaround(jsondate_object, resformat)
    return datetime_object


def datetime_workaround(data, str_format):
    try:
        datetime_object = datetime.strptime(data, str_format)
    except:
        datetime_object = datetime(*(time.strptime(data, str_format)[0:6]))
    return datetime_object


def sort_list(sort_key, sort_direction, list_data):
    try:
        reverse = sort_direction != "asc"
        if sort_key == "rank":
            return sorted(list_data, key=lambda x: x["rank"], reverse=reverse)
        if sort_key == "added":
            return sorted(list_data, key=lambda x: x["listed_at"], reverse=reverse)
        if sort_key == "title":
            return sorted(
                list_data,
                key=lambda x: title_key(x[x["type"]].get("title")),
                reverse=reverse,
            )
        if sort_key == "released":
            return sorted(
                list_data, key=lambda x: released_key(x[x["type"]]), reverse=reverse
            )
        if sort_key == "runtime":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("runtime", 0), reverse=reverse
            )
        if sort_key == "popularity":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("votes", 0), reverse=reverse
            )
        if sort_key == "percentage":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("rating", 0), reverse=reverse
            )
        if sort_key == "votes":
            return sorted(
                list_data, key=lambda x: x[x["type"]].get("votes", 0), reverse=reverse
            )
        if sort_key == "random":
            return sorted(list_data, key=lambda k: random.random())
        return list_data
    except:
        return list_data


def released_key(item):
    if "released" in item:
        return item["released"] or "2050-01-01"
    if "first_aired" in item:
        return item["first_aired"] or "2050-01-01"
    return "2050-01-01"


def title_key(title):
    try:
        if title is None:
            title = ""
        articles = ["the", "a", "an"]
        match = re.match(r"^((\w+)\s+)", title.lower())
        if match and match.group(2) in articles:
            offset = len(match.group(1))
        else:
            offset = 0
        return title[offset:]
    except:
        return title


def sort_for_article(_list, _key):
    _list.sort(key=lambda k: re.sub(r"(^the |^a |^an )", "", k[_key].lower()))
    return _list



