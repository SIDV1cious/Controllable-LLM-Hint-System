from pathlib import Path

import setuptools

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setuptools.setup(
    name="streamlit-component-x",
    version="0.0.1",
    author="SIDV1cious",
    description="MathLive input component for the controllable LLM hint system.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/SIDV1cious/Controllable-LLM-Hint-System",
    packages=setuptools.find_packages(),
    include_package_data=True,
    classifiers=[
        "Framework :: Streamlit",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.11",
    install_requires=[
        "streamlit>=1.58,<2",
    ],
    extras_require={
        "devel": [
            "wheel",
            "pytest==9.0.3",
            "playwright==1.48.0",
            "requests==2.33.0",
            "pytest-playwright-snapshot==1.0",
            "pytest-rerunfailures==12.0",
        ]
    },
)
