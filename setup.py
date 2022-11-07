import os

from setuptools import find_packages
from setuptools import setup

with open(os.path.join(os.path.dirname(__file__), "README.md")) as readme:
    README = readme.read()

os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

setup(
    name="django-stomp",
    version="5.1.1",
    description="A simple implementation of STOMP with Django",
    long_description=README,
    long_description_content_type="text/markdown",
    include_package_data=True,
    author="Ricardo Baltazar Chaves, Willian Antunes",
    author_email="Ricardo Baltazar <ricardobchaves6@gmail.com>, Willian Antunes <willian.lima.antunes@gmail.com>",
    license="MIT",
    url="https://github.com/juntossomosmais/django-stomp",
    packages=find_packages(),
    install_requires=["request-id-django-log==0.1.1", "stomp.py~=7.0", "tenacity~=8.0"],
    classifiers=[
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Framework :: Django :: 2.1",
        "Environment :: Web Environment",
        "Natural Language :: Portuguese (Brazilian)",
        "Development Status :: 5 - Production/Stable",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
