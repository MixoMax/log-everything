from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="atlogger",
    version="0.1.2",
    packages=find_packages(),
    install_requires=requirements,
    author="Linus Horn",
    author_email="linus@linush.org"
)