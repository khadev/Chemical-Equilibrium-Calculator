from setuptools import setup, find_packages
import os

# Read README_PYPI.md
this_directory = os.path.abspath(os.path.dirname(__file__))
readme_path = os.path.join(this_directory, "README_PYPI.md")

if os.path.exists(readme_path):
    with open(readme_path, encoding="utf-8") as f:
        long_description = f.read()
else:
    long_description = "Chemical Equilibrium Calculator"

setup(
    name="chem-eq-calculator",
    version="1.1.2",
    author="Oukil Khaled Ibn Elwalid",
    author_email="oukil.khaled@gmail.com",
    description="Chemical Equilibrium Calculator",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license="GPL-3.0",
    python_requires=">=3.11",
    install_requires=[
        "PySide6>=6.6.0",
        "matplotlib>=3.7.0",
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "qtawesome>=1.3.0",
    ],
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "chem-eq-calculator=chem_eq_calculator:main",
        ],
    },
)
