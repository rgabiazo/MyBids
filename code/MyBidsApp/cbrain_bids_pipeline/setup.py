import os
import tomllib
from setuptools import setup, find_packages

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
OPENAPI_PATH  = os.path.join(
    PROJECT_ROOT,
    "bids_cbrain_runner", "api", "cbrain_openapi"
)

# Parse version from pyproject.toml so release bumps need only modify that file
PYPROJECT_PATH = os.path.join(PROJECT_ROOT, "pyproject.toml")
with open(PYPROJECT_PATH, "rb") as fp:
    VERSION = tomllib.load(fp)["project"]["version"]

setup(
    name="bids_cbrain_runner",
    version=VERSION,
    packages=find_packages(),
    install_requires=[
        "requests>=2.20",
        "paramiko>=2.7",
        "PyYAML>=5.4",
        "urllib3>=1.26",
        "certifi",
        "python-dateutil",
        "six",
        "pydantic>=2.0",
        "typing-extensions>=4.7",
        # pull in local OpenAPI package
        f"openapi-client @ file://{OPENAPI_PATH}",
    ],
    entry_points={
        "console_scripts": [
            "bids-cbrain-cli=bids_cbrain_runner.cli:main",
            "cbrain-cli=bids_cbrain_runner.cli:main",
        ],
    },
)
