# Project Tailor
Script to parse ordered list of yaml config files and tailor external files using keys from resolved configs
** special thanks to @bhasvanth for initial concept

# Typical Usage
Create yaml files separated for easy reuse and administration then parse using a few predefined keys and list of configs

direct from source, e.g
``` bash
python3 tailor.py --config-files app.yml product.yml cloud.yml --defaults branch=develop region=us-east-1 --tailor-files 'terraform/tailor-template-*.tfvars' 'sql/tailor-template-bootstrap.sql' 'yarn-build-output/*.js'
```
... or via container (in a build/deploy pipeline), e.g
``` bash
tf_env=uat
git_repo_root=$(git rev-parse --show-toplevel)
docker run --rm --user $(id -u):$(id -g) -v ${git_repo_root}:${git_repo_root} ghcr.io/tailor-template/tailor:latest --config-files ${git_repo_root}/app.yml ${git_repo_root}/config/product.yml ${git_repo_root}/config/cloud.yml --defaults environment=${tf_env} --tailor-files "${git_repo_root}/terraform/ci/tailor-template-*.tfvars" --resolved-file ${git_repo_root}/tailor.yml
```

* cloud.yml - all of your cloud accounts, environments, networking etc.  basically anything that is the same across all product lines.  this config file would be located in a central area and pulled for each build/deploy.  perhaps in the same location as the tailor.py script ?
* product.yml - anything that is consistent within a product but not specific to a single application.  this file would be listed prior to the global config so that it's values can override the global ones of the same key name.  this file would be in a central location for the product
* app.yml - unique to this application.  this file would be listed first to insure it's values override any values found in other configs

** see examples in tst* directrory

# Auxiliary tools
Generate a cloud.yml file from an existing AWS account.  These can be concatenated together and placed under structure:
``` yaml
config:
  account_name:
```
To generate the YAML config for an account, run:
``` bash
docker run -v ~/.aws:/root/.aws -e AWS_PROFILE=some_aws_account_profile --rm --entrypoint /usr/local/bin/python3 ghcr.io/tailor-template/tailor:latest /usr/src/app/gen-aws-env.py > aws_account_name.yml
```

# ToDo
* allow configs to be URLs
* add default path like script-dir for config file lookup if not in cwd
* create fully working example application and configs for an AWS environment using terraform
* fix bug where keys whose value type is bool are ignored

