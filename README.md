# Project tailor
Script to parse order list of yaml config files and tailor external files using keys from resolved configs

# ssage
create yaml files separated for easy reuse and administration
e.g
cloud.yml - all of your cloud accounts, environments, networking etc.  basically anything that is the same across all product lines.  this file would be located in a central area and pulled for each build/deploy.  perhaps in the same location as the tailor.py script
product.yml - anything that is consistent within a product but not specific to a single