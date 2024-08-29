import setuptools
from distutils.core import setup
#python setup.py bdist_wheel --universal


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="NorenRestApi",
    version="0.0.31",
    author="KumarAnand",
    author_email="kumar.anand@kambala.co.in",
    description="A package for NorenOMS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ],
 install_requires=[
    "requests",
    "websocket-client",
    "pandas",
    "PyYAML",
    ],
)



