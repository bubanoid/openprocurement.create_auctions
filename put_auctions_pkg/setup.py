from setuptools import setup
setup(name='put_auctions',
      py_modules=['put_auctions'],
      install_requires=['python-dateutil', 'gevent', 'iso8601',
                        'configparser'])
