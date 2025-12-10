from setuptools import setup, find_packages

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="gchat_integration",
    version="0.0.1",
    description="Google Chat Integration for Frappe",
    author="BEI Tech",
    author_email="sam@bebang.ph",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)

