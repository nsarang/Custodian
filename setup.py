import re

from setuptools import find_packages, setup

with open("custodian/__init__.py", encoding="utf-8") as fh:
    content = fh.read()
    version = re.search(r"__version__\s*=\s*([\"\'])(.+?)\1", content).group(2)

with open("README.md", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements/app.txt", encoding="utf-8") as fh:
    app_dependencies = fh.read().splitlines()

setup(
    name="custodian",
    version=version,
    packages=find_packages(),
    install_requires=app_dependencies,
    python_requires=">=3.8",
    author="Nima Sarang",
    author_email="contact@nimasarang.com",
    description="A Python library for financial transaction processing and analysis.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nsarang/custodian",
    project_urls={
        "Homepage": "https://github.com/nsarang/custodian",
        "Issues": "https://github.com/nsarang/custodian/issues",
        "Documentation": "https://github.com/nsarang/custodian#readme",
    },
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Debuggers",
    ],
    keywords="finance, transactions, portfolio, analysis, accounting",
)
