# https://github.com/cloudfoundry-community/terraform-aws-cf-net/blob/master/terraform.tfvars.example
aws_access_key = "XXXXXXXXXXXXXXXXXXXX"
aws_secret_key = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
aws_key_path = "~/.ssh/bosh.pem"
aws_key_name = "bosh"
aws_region = "us-east-1"
network = "10.10"
aws_account_alias = "{{ account_name }}"
# These most often come from terraform-aws-vpc, but can be manually set
# if you don't want to or can't use that module.
aws_route_table_private_id = "X"
aws_internet_gateway_id = "X"
aws_route_table_public_id = "X"
aws_vpc_id = "X"