#!/usr/bin/python3

# examples:
#   python3 gen-aws-env.py

import os
import re
import sys
import argparse
import logging
import traceback
import yaml
import boto3

# get command line args
parser = argparse.ArgumentParser()
parser.add_argument("--scan-results-file", type=str, default="aws-cloud.yml", help="output file name (default aws-cloud.yml)", required=False)
parser.add_argument("--verbose", default=False, help="add verbose messaging (default false)", required=False, action='store_true')
parser.add_argument("--best-effort", default=False, help="best effort to determine public/private subnets (default false)", required=False, action='store_true')

try:
    args = parser.parse_args()
except Exception:
    parser.print_help()
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
    if verbose:
        logger.info("logger verbosity set to DEBUG")
    return logging.getLogger(os.path.basename(__file__))


#-------------------------------------------------------------------------------
# print resolved structure to yaml file
#-------------------------------------------------------------------------------
def print_config_map(resolved_paramers_filename, config_map):
    logger.info(f"writing configs to {resolved_paramers_filename}")
    with open(resolved_paramers_filename, 'w') as f:
        yaml.dump({"config": {"account_name": config_map}}, f)


#-------------------------------------------------------------------------------
# get account information
#-------------------------------------------------------------------------------
def get_aws_account_info():
    account_id = boto3.client('sts').get_caller_identity()["Account"]
    account_name = account_id
    for account_alias in boto3.client('iam').list_account_aliases()['AccountAliases']:
        account_name = account_alias
        break
    return(account_name, account_id)


#-------------------------------------------------------------------------------
# get list of all usable regions
#-------------------------------------------------------------------------------
def get_aws_regions():
    try:
        response = boto3.client('ec2').describe_regions()
        regions = [r["RegionName"] for r in response["Regions"]]
    except Exception:
        logger.error("Could not get regions")
        sys.exit(traceback.print_exc())
    return regions


#-------------------------------------------------------------------------------
# get list of all vpcs in region
#-------------------------------------------------------------------------------
def get_vpcs(client: boto3.client, region: str):
    try:
        response = client.describe_vpcs()
        vpcs = [v["VpcId"] for v in response["Vpcs"]]
    except Exception:
        logger.error(f"could not get vpcs in region {region}")
        logger.debug(traceback.print_exc())
        vpcs = []
    return vpcs


#-------------------------------------------------------------------------------
# get list of all vpcs in region
#-------------------------------------------------------------------------------
def get_vpc_subnets(client: boto3.client, vpc: str, region: str):
    subnets = []
    public_subnets = []
    private_subnets = []
    try:
        response = client.describe_subnets(Filters=[{'Name': 'vpc-id','Values': [vpc]}])
        for subnet in response["Subnets"]:
            subnet_name = ''
            subnet_id = subnet['SubnetId']
            if 'Tags' in subnet:
                for tag in subnet['Tags']:
                    if tag['Key'] == 'Name':
                        subnet_name = tag['Value']
                        if args.best_effort:
                            # if subnet tag value has the substring public in it, assume it is a public subnet and add to public_subnet list
                            if 'public' in tag['Value'].lower():
                                public_subnets.append(subnet_id)
                            if 'private' in tag['Value'].lower():
                                private_subnets.append(subnet_id)
                        break
            subnets.append({subnet_id: {'subnet_name': subnet_name, 'cidr': subnet['CidrBlock'], 'az': subnet['AvailabilityZone']}})
    except Exception:
        logger.error(f"could not get vpcs in region {region}")
        sys.exit(traceback.print_exc())
    return (subnets, private_subnets, public_subnets)


#-------------------------------------------------------------------------------
# get list of nat gateway ip addresses
#-------------------------------------------------------------------------------
def get_nat_gateway_ips(client: boto3.client, vpc: str, region: str):
    nat_gateway_ips = []
    try:
        response = client.describe_nat_gateways(Filters=[{'Name': 'vpc-id','Values': [vpc]}])
        nat_gateway_ips = [n["NatGatewayAddresses"][0]['PublicIp'] for n in response["NatGateways"]]
    except Exception:
        logger.error(f"could not get nat gateways for vpc {vpc} in region {region}")
        sys.exit(traceback.print_exc())
    return nat_gateway_ips


#-------------------------------------------------------------------------------
# get list of all vpcs in region
#-------------------------------------------------------------------------------
def get_vpc_info(client: boto3.client, vpc: str, region: str):
    vpc_info = { 'defaults': {}, 'subnet': []}
    try:
        response = client.describe_vpcs(VpcIds=[vpc])
        vpc_info['defaults']['vpc_cidrs'] = ','.join([c["CidrBlock"] for c in response['Vpcs'][0]["CidrBlockAssociationSet"]])
        vpc_info['defaults']['is_default'] = response['Vpcs'][0]['IsDefault']
        vpc_info['defaults']['vpc_name'] = ''
        if 'Tags' in response['Vpcs'][0]:
            for tag in response['Vpcs'][0]['Tags']:
                if tag['Key'] == 'Name':
                    vpc_info['defaults']['vpc_name'] = tag['Value']
                    break
        (subnets, private_subnets, public_subnets) = get_vpc_subnets(client, vpc, region)
        nat_gw_ips = get_nat_gateway_ips(client, vpc, region)
        vpc_info['subnet'] = subnets
        if args.best_effort:
            if private_subnets:
                vpc_info['defaults']['private_subnets'] = ','.join(private_subnets)
            if public_subnets:
                vpc_info['defaults']['public_subnets'] = ','.join(public_subnets)
        vpc_info['defaults']['nat_gw'] = ','.join(nat_gw_ips)
        vpc_info['defaults']['nat_gw'] = ','.join(nat_gw_ips)
    except Exception:
        logger.error(f"could not get vpc information for {vpc} in region {region}")
        sys.exit(traceback.print_exc())
    return vpc_info


#-------------------------------------------------------------------------------
# scan vpc information in each region and create map
#-------------------------------------------------------------------------------
def map_aws_cloud_environment():
    (account_name, account_id) = get_aws_account_info()
    account_info = {account_name: {'defaults': {'account_id': account_id}, 'region': {}}}
    regions = get_aws_regions()

    logger.debug(f"scanning regions: {regions}")
    for region in regions:
        account_info[account_name]['region'][region] = {'vpc': {}}
        account_info_vpc = account_info[account_name]['region'][region]['vpc']
        try:
            ec2_client = boto3.client('ec2', region_name=region)
            vpcs = get_vpcs(ec2_client, region)
            for vpc in vpcs:
                vpc_info = get_vpc_info(ec2_client, vpc, region)
                account_info_vpc[vpc] = vpc_info
                # if vpc_info is empty, remove vpc from account_info_vpc
                if not account_info_vpc[vpc]:
                    del account_info_vpc[vpc]
        except Exception:
            logger.error("could not get regions")
            sys.exit(traceback.print_exc())
        finally:
            # if region does not have any vpcs, remove region from account_info
            if not account_info_vpc:
                del account_info[account_name]['region'][region]

    print(f"{yaml.dump(account_info)}")
    return account_info


#-------------------------------------------------------------------------------
# Run
#-------------------------------------------------------------------------------
if __name__ == "__main__":
    logger = setup_logger(args.verbose)
    aws_cloud_environment = map_aws_cloud_environment()
    print_config_map(args.scan_results_file, aws_cloud_environment)
    sys.exit(0)
