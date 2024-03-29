from setuptools import setup, find_packages

PROJECT_NAME = 'parrotGPT'
VERSION = '0.0.1'

setup(name=PROJECT_NAME,
      version=VERSION,
      entry_points={
          'console_scripts': [
              'manager = manager:main'
          ]
      },
      license='MIT',
      packages=find_packages(),
      install_requires=[
          'openai==1.3.7',
          'fastapi==0.100.1',
          'requests==2.27.1',
          'uvicorn',
          'pydantic==2.1.1',
          'nltk==3.8.1',
          'fire==0.4.0',
          'python-crontab==2.6.0',
          'setuptools~=65.5.0',
          'crontab~=0.23.0',
          'pytz',
          'sseclient',
          "redis==4.2.1",
          "simplejson==3.17.6"
      ],
      zip_safe=False
      )
