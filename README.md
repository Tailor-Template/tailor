# Project tailor
Script to parse order list of yaml config files and tailor external files using keys from resolved configs

# Usage
Create yaml files separated for easy reuse and administration then parse using a few predefined keys and list of configs

e.g
``` code
python3 tailor.py --config-files app.yml product.yml cloud.yml --defaults branch=develop region=us-east-1 --tailor-files 'terraform/tailor-template-*.tfvars' 'sql/tailor-template-bootstrap.sql' 'yarn-build-output/*.js'
```

* cloud.yml - all of your cloud accounts, environments, networking etc.  basically anything that is the same across all product lines.  this config file would be located in a central area and pulled for each build/deploy.  perhaps in the same location as the tailor.py script ?
* product.yml - anything that is consistent within a product but not specific to a single application.  this file would be listed prior to the global config so that it's values can override the global ones of the same key name.  this file would be in a central location for the product
* app.yml - unique to this application.  this file would be listed first to insure it's values override any values found in other configs

** see examples in tst* directrory

# ToDo
* allow configs to be URLs
* add default path like script-dir for config file lookup if not in cwd
* create fully working example application and configs for an AWS environment using terraform

