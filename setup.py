import setuptools
from distutils.core import setup
#python setup.py bdist_wheel --universal


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="NorenRestApi",
    version="0.0.29",
    author="KumarAnand",
    author_email="kumar.anand@kambala.co.in",
    description="A package for NorenOMS",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=(
        "Programming Language :: Python :: 3",
        "License :: Other/Proprietary License",
        "Operating System :: OS Independent",
    ),
 install_requires=[
    "requests==2.28.2",
    "websocket-client==1.5.1",
    "pandas==1.5.3",
    "PyYAML==6.0.1",
    ],
)



