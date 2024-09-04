import os

from setuptools import find_packages
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), "README.md")) as readme:
    README = readme.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name="django-stomp",
    version="6.1.0",
    description="A simple implementation of STOMP with Django",
    long_description=README,
    long_description_content_type="text/markdown",
    include_package_data=True,
    author="Ricardo Baltazar Chaves, Willian Antunes",
    author_email="Ricardo Baltazar <ricardobchaves6@gmail.com>, Willian Antunes <willian.lima.antunes@gmail.com>",
    license="MIT",
    url="https://github.com/juntossomosmais/django-stomp",
    packages=find_packages(exclude=("tests", "tests.*")),
    install_requires=["request-id-django-log==0.2.0", "stomp.py~=8.0", "tenacity~=8.0"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.10",
        "Framework :: Django :: 5.1",
        "Environment :: Web Environment",
        "Natural Language :: Portuguese (Brazilian)",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
