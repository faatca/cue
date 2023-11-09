import re


def validate_key(value):
    if not value:
        return "key is required"
    if not isinstance(value, str):
        return "key must be a string"
    if len(value) > 50:
        return "key is too long"
    if len(value) < 5:
        return "key is too short"
    if not value.isalnum():
        return "key has invalid format"
    return None


def validate_key_id(value):
    if not value:
        return "key id is required"
    if not isinstance(value, str):
        return "key id must be a string"
    if len(value) > 50:
        return "key id is too long"
    if len(value) < 5:
        return "key id is too short"
    if not re.fullmatch(r"[0-9A-Fa-f-]+", value):
        return "key id has invalid format"
    return None


def validate_key_name(value):
    if not value:
        return "key name is required"
    if not isinstance(value, str):
        return "key name must be a string"
    if len(value) > 1024:
        return "key name is too long"
    return None


def validate_cue_name(value):
    if not value:
        return "cue name is required"
    if not isinstance(value, str):
        return "cue name must be a string"
    if len(value) > 1024:
        return "cue name is too long"
    return None


def validate_cue_pattern(value):
    if not value:
        return "cue pattern is required"
    if not isinstance(value, str):
        return "cue pattern must be a string"
    if len(value) > 1024:
        return "cue pattern is too long"
    return None
