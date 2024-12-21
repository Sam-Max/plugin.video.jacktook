import hashlib
import json


def serialize_sets(obj):
    return sorted([str(i) for i in obj]) if isinstance(obj, set) else obj


def valid_id_or_none(id_number):
    """
    Helper function to check that an id number from an indexer is valid
    Checks if we have an id_number and it is not 0 or "0"
    :param id_number: The id number to check
    :return: The id number if valid, else None
    """
    return id_number if id_number and id_number != "0" else None


def md5_hash(value):
    """
    Returns MD5 hash of given value
    :param value: object to hash
    :type value: object
    :return: Hexdigest of hash
    :rtype: str
    """
    if isinstance(value, (tuple, dict, list, set)):
        value = json.dumps(value, sort_keys=True, default=serialize_sets)
    return hashlib.md5(str(value).encode("utf-8")).hexdigest()


def extend_array(array1, array2):
    """
    Safe combining of two lists
    :param array1: List to combine
    :type array1: list
    :param array2: List to combine
    :type array2: list
    :return: Combined lists
    :rtype: list
    """
    result = []
    if array1 and isinstance(array1, list):
        result.extend(array1)
    if array2 and isinstance(array2, list):
        result.extend(array2)
    return result
