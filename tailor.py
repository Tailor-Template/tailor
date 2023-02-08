#!/usr/bin/python3

# examples:
#    python3 tailor.py --config-files tst0/config-first.yml tst0/config-second.yml tst0/config-third.yml --defaults account=account-alias-1 environments=prod region=us-east-1 --verbose

import os
import sys
import argparse
import logging
import glob
import re
import traceback
import yaml
import json
import copy

# get command line args
parser = argparse.ArgumentParser()
parser.add_argument("--config-files", nargs='+', default=[], help="list of configuration files in order of precedence", required=True)
parser.add_argument("--tailor-files", nargs='+', default=[], help="List of Glob File Patterns to tailor (default None)", required=False)
parser.add_argument("--defaults", nargs='*', default=[], help="list of key value pairs (default None)", required=False)
parser.add_argument("--ordered-keys", nargs='*', default=[":AWS_DEFAULT:"], help="list of key names to resolve in config files (default :AWS_DEFAULT:)", required=False)
# parser.add_argument("--threads", type=int, default=1, help="Number of Threads (default 1)", required=False)
parser.add_argument("--verbose", default=False, help="add verbose messaging (default false)", required=False, action='store_true')

try:
    args = parser.parse_args()
except Exception:
    parser.print_help()
    sys.exit(traceback.print_exc())

# globals
PRESET_ORDERED_KEYS = {
    "AWS_DEFAULT": ['environment', 'account', 'branch', 'region']
}

#-------------------------------------------------------------------------------
# get ordered list of keys form list matching keyword
#-------------------------------------------------------------------------------
def get_preset_list(preset_list_name):
    if preset_list_name in PRESET_ORDERED_KEYS:
        logger.debug(f"Using preset orderd list '{preset_list_name}': {PRESET_ORDERED_KEYS[preset_list_name]}")
        return PRESET_ORDERED_KEYS[preset_list_name]
    logger.error(f"No preset ordered key list exists for '{preset_list_name}'")
    sys.exit(1)


#-------------------------------------------------------------------------------
# create list of keys to resolve in order of prececence
# if first key matches pattern :LISTNAME: then lookup preset values for LISTNAME
#-------------------------------------------------------------------------------
def get_ordered_keys_list(ordered_keys):
    if (match := re.fullmatch(r':([A-Z_]+):$', ordered_keys[0])) is not None:
        return get_preset_list(match.groups(1)[0])
    return ordered_keys


#-------------------------------------------------------------------------------
# parse all default key values
#-------------------------------------------------------------------------------
def parse_defaults(defaults: list):
    lookup_defaults = {}
    # for key_value_pair in defaults.split(','):
    try:
        for key_value_pair in defaults:
            item = key_value_pair.split('=')
            logger.debug(f"SET: {item[0]}={item[1]}")
            lookup_defaults[item[0]] = item[1]
        return lookup_defaults
    except Exception:
        logger.error(f"could net evaluate {defaults}")
        sys.exit(traceback.print_exc())


#-------------------------------------------------------------------------------
# Set up logger
#-------------------------------------------------------------------------------
def setup_logger(verbose):
    log_level = logging.INFO
    if verbose:
        log_level = logging.DEBUG
    logger_format = '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
    logging.basicConfig(format=logger_format, level=log_level)
    return logging.getLogger(os.path.basename(__file__))


#-------------------------------------------------------------------------------
# get list of config files in order of precidence
#-------------------------------------------------------------------------------
def get_config_files(config_files: list):
    config_files_list = []
    for config_file in config_files:
        if not os.path.isfile(config_file):
            logger.error(f"Config file, {config_file}, does not exist or is not a regular file")
            sys.exit(1)
        config_files_list.append(config_file)
    return config_files_list


#-------------------------------------------------------------------------------
# get list of files to be tailored
#-------------------------------------------------------------------------------
def get_tailor_files(tailor_files: list):
    tailor_files_list = []
    for tailor_file_glob in tailor_files:
        tailor_files_match = glob.glob(tailor_file_glob)
        if not tailor_files_match:
            logger.warning(f"Tailor file pattern, {tailor_file_glob}, does not match any files")
        tailor_files_list.append(tailor_files_match)
    return tailor_files_list


#-------------------------------------------------------------------------------
# read in yaml struction of each configuration file to array of dictonaries
#-------------------------------------------------------------------------------
def read_config_files(config_files: list):
    configs = []
    for config_file in config_files:
        logger.info(f"Parsing config file: {config_file}")
        with open(config_file) as f:
            config = yaml.safe_load(f)
        config['config']['source_config_file'] = config_file
        configs.append(config['config'])
    return configs


#-------------------------------------------------------------------------------
# parse config files and resolve nodes of matching ordered_keys and add to
# resolved_keys
#-------------------------------------------------------------------------------
def resolve_configs(ordered_keys: list, configs: list, resolved_keys: dict):
    fully_resolved = False
    # merge_keys(config, 'resolved', resolved_keys, overwrite=False)
    while not fully_resolved:
        fully_resolved = True
        for config in configs:
            logger.debug(f"Parsing config tree for {config['source_config_file']}")
            resolved_and_collapsed = colapse_and_get_ordered_list_keys(ordered_keys, config, resolved_keys)
            if resolved_and_collapsed:
                fully_resolved = False
            print(resolved_and_collapsed)
            # sys.exit()
        # sys.exit()
    return configs


#-------------------------------------------------------------------------------
# iterate through keys in tree that match ordered_keys (descending) and find
# element matching value for specified key, and bring back to top level,
# including default keys
#-------------------------------------------------------------------------------
def colapse_and_get_ordered_list_keys(ordered_keys: list, config_node: map, resolved_keys: dict):
    resolved_and_collapsed = False
    for key in config_node:
        node = config_node[key]
        for ordered_key in ordered_keys:
            if ordered_key == key:
                # print(f"{ordered_key} --> {key}")
                if ordered_key in resolved_keys:
                    if resolved_keys[ordered_key] not in node:
                        continue
                        print(yaml.dump(config_node))
                        del(config_node[key])
                        print(yaml.dump(config_node))
                    resolved_node = node[resolved_keys[ordered_key]]
                    colapse_and_get_ordered_list_keys(ordered_keys, resolved_node, resolved_keys)

                    # if 'defaults' not in resolved_node:
                    #     resolved_node['defaults'] = {}
                    print("resolving_leaf_keys")
                    # print('--------------------')
                    # print(yaml.dump(node))
                    move_leaf_keys_to_resolved_key_list(resolved_node)
                    move_leaf_keys_to_resolved_key_list(node)
                    merge_keys(node['defaults'], resolved_node['defaults'], True)
                    merge_keys(node['resolved'], resolved_node['resolved'], True)
                    update_resolved_keys(node['resolved'], ordered_keys, resolved_keys)
                    update_resolved_keys(node['defaults'], ordered_keys, resolved_keys)
                    del node[resolved_keys[ordered_key]]
                    # print('--------------------')
                    # print(yaml.dump(node))
                    resolved_and_collapsed = True      # flag that some resolving took place

    return resolved_and_collapsed


#-------------------------------------------------------------------------------
# create new list of resoved keys under node for each leaf, and remove leaf key
#-------------------------------------------------------------------------------
def move_leaf_keys_to_resolved_key_list(node: map):
    if 'resolved' not in node:
        node['resolved'] = {}
    if 'defaults' not in node:
        node['defaults'] = {}
    for key in list(node):
        if isinstance(node[key], str):
            node['resolved'][key] = node[key]
            del(node[key])


#-------------------------------------------------------------------------------
# merge all keys from list_of_keys to node[key_in_node]
#-------------------------------------------------------------------------------
def merge_keys(node_to: map, node_from: map, overwrite: bool):
    for key in node_from:
        if not overwrite and key in node_to:        # if overwrite not true and key already exists, skip
            continue
        node_to[key] = node_from[key]


#-------------------------------------------------------------------------------
# if any new key from keylist exists in ordered list, add to resolved_keys if
# not already present
#-------------------------------------------------------------------------------
def update_resolved_keys(keylist: map, ordered_keys: list, resolved_keys: dict):
    for key in keylist:
        if key in ordered_keys and key not in resolved_keys:
            resolved_keys[key] = keylist[key]
            logger.debug(f"Found ordered key {key} as {keylist[key]}")


#-------------------------------------------------------------------------------
# Run
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    logger = setup_logger(args.verbose)
    resolved_keys = parse_defaults(args.defaults)
    ordered_keys = get_ordered_keys_list(args.ordered_keys)
    # config_files = get_config_files(args.config_files)
    # configs = read_config_files(config_files)
    configs = read_config_files(args.config_files)
    resolved_config = resolve_configs(ordered_keys, copy.deepcopy(configs), resolved_keys)
    tailor_files = get_tailor_files(args.tailor_files)
    sys.exit(0)
