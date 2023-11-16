#!bin/bash

python3 -m venv venv
source venv/bin/activate

pip install pyyaml
pip install nipyapi==0.19.0
pip install "ruamel.yaml<0.18.0"

