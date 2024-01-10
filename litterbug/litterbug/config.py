from __future__ import annotations

import importlib.resources as resources
from typing import Any, Dict, List, Union

import yaml


class LitterbugConfig:
    """
    LitterbugConfig is a class dedicated to loading and managing
    configuration for Litterbug and sub modules. It also
    provides save/write functionality for configurations.

    A default configuration file (default_config.yaml in the
    package) is provided and merged with choices. Type checking
    is loose so beware. Nesting of attributes is allowed and
    handled.
    """

    def __init__(self, attributes: Dict[str, Any] = {}):
        self.attributes: Dict[str, Any] = attributes

        with resources.open_text("litterbug", "default_config.yaml") as f:
            raw = f.read()
            default_attributes = yaml.safe_load(raw)

        self.attributes = self.__merge_setting(default_attributes, attributes)

    def __merge_setting(
        self, base: Dict[str, Any], incoming: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Merges a setting into the attributes dict
        """
        # First, determine that there are no keys in the incoming
        # that do not exist in the base - we disallow it as a config
        # that has unused values may be doing something unexpected
        # and *should* fail
        for key, value in incoming.items():
            if key not in base:
                raise UnknownConfigKey(key)

        # Now we begin combining the base into our incoming
        for key, value in base.items():
            # If it's blank accept base value
            if key not in incoming:
                incoming[key] = value
            elif type(value) is type(incoming[key]):
                # Otherwise, type check. If it's not the same
                # type, we error out
                raise ConfigTypeError(key, type(value), type(incoming[key]))
            elif isinstance(value, dict):
                # If it's a dict, we need to nest further down
                # recursively. If we get an exception, bubble it
                # up but append our key information for accurate
                # tracking of the problematic key
                try:
                    self.__merge_setting(value, incoming[key], key, value)
                except ConfigTypeError as e:
                    raise ConfigTypeError([key] + e.keys, e.type_expected, e.type_found)
                except UnknownConfigKey as e:
                    raise UnknownConfigKey([key] + e.keys)

        return incoming

    def __getitem__(self, key: str) -> Any:
        """
        We return the attribute if it exists, returning
        UnknownConfigKey if it does not. Note that we aim
        to support "." as a delimiter for deeper search
        """
        if "." in key:
            keys = key.split(".")
            current = self.attributes
            for subkey in keys:
                if subkey not in current:
                    matches = self.__close_attributes(key)
                    raise UnknownAttribute(key, matches)
                else:
                    current = current[subkey]
            return current
        elif key not in self.attributes:
            matches = self.__close_attributes(key)
            raise UnknownAttribute(key, matches)
        else:
            return self.attributes[key]

    def __close_attributes(self, attr: str) -> List[str]:
        """
        Given a string attribute, determine which of all attributes it
        is lexicographically close to if any
        """

        # This is generally taken from Peter Norvig via
        # http://norvig.com/spell-correct.html

        # First we create a set of edits on the attr
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        alphabet += "0123456789_-."

        splits = [(attr[:i], attr[i:]) for i in range(len(attr) + 1)]
        deletes = [a + b[1:] for a, b in splits if b]
        transposes = [a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1]
        replaces = [a + c + b[1:] for a, b in splits for c in alphabet if b]
        inserts = [a + c + b for a, b in splits for c in alphabet]
        edits = set(deletes + transposes + replaces + inserts)

        # Create a list of all keys
        keys = []
        dicts: Dict[str, Dict[str, Any]] = {"": self.attributes}
        current_key = ""
        while len(dicts) > 0:
            current_key = dicts.keys()[0]
            current = dicts[current_key]
            del dicts[current_key]
            for key in current.keys():
                if type(current[key]) is dict:
                    dicts = current[key]
                else:
                    keys.append(f"{current_key}.{key}")

        # Determine which words if any match the edits
        matches = []
        for word in self.attributes.keys():
            if word in edits:
                matches.append(word)

        return matches

    def FromYAML(self, filepath: str) -> LitterbugConfig:
        """
        Read a CSV file and create a config with its attributes
        """
        with open(filepath, "r") as f:
            raw = f.read()
            attributes = yaml.safe_load(raw)

        return LitterbugConfig(attributes)

    def ToYAML(self, filepath: str) -> None:
        """
        Write a CSV file with the config's attributes
        """
        with open(filepath, "w") as f:
            yaml.dump(self.attributes, f)


class UnknownAttribute(Exception):
    """
    UnknownAttribute is an exception that is raised when an attribute
    is attempted to be retrieved from a config, but it does not exist.
    """

    def __init__(self, attribute: str, matches: List[str]):
        self.attribute = attribute
        self.matches = matches

    def __str__(self):
        if len(self.matches) < 1:
            return f"Unknown attribute {self.attribute}"
        elif len(self.matches) == 1:
            return (
                f"Unknown attribute {self.attribute}; did you mean {self.matches[0]}?"
            )
        else:
            return f"Unknown attribute {self.attribute}; did you mean one of [{self.matches}]?"


class ConfigTypeError(Exception):
    """
    ConfigTypeError is an exception that is raised if the default
    config specifies that a given setting should have a different
    type.
    """

    def __init__(
        self, keys: Union[str, List[str]], type_expected: str, type_found: str
    ):
        if keys is str:
            keys = [keys]
        self.keys = keys
        self.type_expected = type_expected
        self.type_found = type_found

    def __str__(self):
        key = ".".join(self.keys)
        return f"Expected {self.type_expected} for {key}, but found {self.type_found}"


class UnknownConfigKey(Exception):
    """
    UnknownConfigKey is thrown when an incoming configuration set
    values that are unknown to the default and thus not applicable.
    """

    def __init__(self, keys: Union[str, List[str]]):
        self.keys = keys

    def __str__(self):
        key = ".".join(self.keys)
        return f"Unknown config key {key}"
