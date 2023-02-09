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
import copy
import json
import yaml

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
    "AWS_DEFAULT": ['environment', 'account_name', 'branch', 'region']
}

#-------------------------------------------------------------------------------
# get ordered list of keys form list matching keyword
#-------------------------------------------------------------------------------
def get_preset_list(preset_list_name):
    if preset_list_name in PRESET_ORDERED_KEYS:
        logger.debug(f"Using preset ordered list '{preset_list_name}': {PRESET_ORDERED_KEYS[preset_list_name]}")
        return PRESET_ORDERED_KEYS[preset_list_name]
    logger.error(f"No preset ordered key list exists for '{preset_list_name}'")
    sys.exit(1)


#-------------------------------------------------------------------------------
# create list of keys to resolve in order of prececence
# if first key matches pattern :LISTNAME: then lookup preset values for LISTNAME
#-------------------------------------------------------------------------------
def get_resolvable_keys_list(resolvable_keys):
    if (match := re.fullmatch(r':([A-Z_]+):$', resolvable_keys[0])) is not None:
        return get_preset_list(match.groups(1)[0])
    return resolvable_keys


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
        config['config']['resolved'] = {'source_config_file': config_file}
        configs.append(config['config'])
    return configs


#-------------------------------------------------------------------------------
# create a single structure to represent all config resolution
#-------------------------------------------------------------------------------
def consolidate_configs(configs: list, resolved_keys: dict):
    consolidated_config = {'config': {}}
    for config in reversed(configs):
        logger.debug(f"Adding resolved values from {config['resolved']['source_config_file']}")
        merge_keys(config['defaults'], config['resolved'], True)
        merge_keys(consolidated_config['config'], config['defaults'], True)
    merge_keys(consolidated_config['config'], resolved_keys, True)
    return consolidated_config


#-------------------------------------------------------------------------------
# parse config files and resolve nodes of matching resolvable_keys and add to
# resolved_keys
#-------------------------------------------------------------------------------
def resolve_configs(resolvable_keys: list, configs: list, resolved_keys: dict):
    fully_resolved = False
    while not fully_resolved:
        fully_resolved = True
        for config in configs:
            logger.debug(f"Parsing config tree for {config['resolved']['source_config_file']}")
            resolution_occured = colapse_and_get_ordered_list_keys(resolvable_keys, config, resolved_keys)
            if resolution_occured:
                fully_resolved = False
    return configs


#-------------------------------------------------------------------------------
# check if any unresolved orderd keys are in list
#-------------------------------------------------------------------------------
def check_for_unresolved_resolvable_keys(resolvable_keys: list, config_node: map):
    for resolvable_key in resolvable_keys:
        if resolvable_key in config_node:
            if not isinstance(config_node[resolvable_key], (str, int, float)):
                return True
    return False


#-------------------------------------------------------------------------------
# iterate through keys in tree that match resolvable_keys (descending) and find
# element matching value for specified key, and bring back to top level
# as default keys
#-------------------------------------------------------------------------------
def colapse_and_get_ordered_list_keys(resolvable_keys: list, config_node: map, resolved_keys: dict):
    move_leaf_keys_to_resolved_key_list(config_node)
    resolution_occured = False
    for key in list(config_node):
        if key in ['resolved', 'defaults']:
            continue
        if key not in resolvable_keys:
            logger.warning(f"Unknown element structure '{key}' nested in {yaml.dump(config_node)}")
        node = config_node[key]
        move_leaf_keys_to_resolved_key_list(node)
        for resolvable_key in resolvable_keys:
            if key == resolvable_key:                                                  # is key that should be resolvable
                if key in resolved_keys:                                            # key has resolvable value
                    merge_keys(node['defaults'], node['resolved'], True)
                    merge_keys(config_node['defaults'], node['defaults'], True)
                    if resolved_keys[key] not in node:                      # value does not exist in list, cannot be resolved
                        del(config_node[key])
                        resolution_occured = True
                        continue

                    resolved_node = node[resolved_keys[key]]
                    resolution_occured = colapse_and_get_ordered_list_keys(resolvable_keys, resolved_node, resolved_keys)

                    # if there are unresolved sub structures that are resolvable, do no delete this node
                    if check_for_unresolved_resolvable_keys(resolvable_keys, resolved_node):
                        logger.info(f"found more ordered keys in {resolved_keys[key]}\n:{yaml.dump(resolved_node)}")
                        break

                    move_leaf_keys_to_resolved_key_list(resolved_node)
                    merge_keys(resolved_node['defaults'], resolved_node['resolved'], True)
                    # merge_keys(node['defaults'], node['resolved'], True)
                    merge_keys(node['defaults'], resolved_node['defaults'], True)
                    merge_keys(config_node['defaults'], node['defaults'], True)
                    update_resolved_keys(config_node['defaults'], resolvable_keys, resolved_keys)
                    del(config_node[key])
                    resolution_occured = True

    return resolution_occured


#-------------------------------------------------------------------------------
# create new list of resoved keys under node for each leaf, and remove leaf key
#-------------------------------------------------------------------------------
def move_leaf_keys_to_resolved_key_list(node: map):
    if 'resolved' not in node:
        node['resolved'] = {}
    if 'defaults' not in node:
        node['defaults'] = {}
    for key in list(node):
        if isinstance(node[key], (str, int, float)):
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
def update_resolved_keys(keylist: map, resolvable_keys: list, resolved_keys: dict):
    for key in keylist:
        if key in resolvable_keys and key not in resolved_keys:
            resolved_keys[key] = keylist[key]
            logger.debug(f"Found ordered key {key} as {keylist[key]}")


#-------------------------------------------------------------------------------
# Run
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    logger = setup_logger(args.verbose)
    resolved_keys = parse_defaults(args.defaults)
    resolvable_keys = get_resolvable_keys_list(args.ordered_keys)
    # config_files = get_config_files(args.config_files)
    # configs = read_config_files(config_files)
    configs = read_config_files(args.config_files)
    resolved_config = resolve_configs(resolvable_keys, copy.deepcopy(configs), resolved_keys)
    config_map = consolidate_configs(resolved_config, resolved_keys)
    print(yaml.dump(config_map))
    tailor_files = get_tailor_files(args.tailor_files)
    sys.exit(0)
