import tomllib
from setuptools import setup, find_packages

# Safely read the long description from README.md, if present
try:
    with open("README.md", encoding="utf-8") as f:
        long_description = f.read()
except FileNotFoundError:
    long_description = ""

# Parse version from pyproject.toml so release bumps need only modify that file
with open("pyproject.toml", "rb") as fp:
    VERSION = tomllib.load(fp)["project"]["version"]

setup(
    name="dicomatic",
    version=VERSION,
    description="A DICOM Query & Download CLI tool for BIDS datasets",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="you@example.com",
    url="https://github.com/yourusername/dicomatic",
    packages=find_packages(include=["dicomatic", "dicomatic.*"]),
    python_requires=">=3.7",
    install_requires=[
        "ruamel.yaml>=0.17.21",
        "click>=8.0",
        "tableprint>=0.9.0",      # ← add this line
    ],
    entry_points={
        "console_scripts": [
            # Point to the "cli" function in dicomatic/cli.py
            "dicomatic-cli = dicomatic.cli:cli",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
