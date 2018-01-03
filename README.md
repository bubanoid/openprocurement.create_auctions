> virtualenv --no-setuptools --clear /path/to/clean_env
> . /path/to/clean_env/bin/activate
> python bootstrap.py --setuptools-version 38.2.4 --buildout-version 2.10.0
> bin/buildout
> deactivate
> bin/put_auctions_insider.py
