import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aiotus",
    version="0.1.0",
    author="Jens Steinhauser",
    author_email="jens.steinhauser@gmail.com",
    description="Asynchronous tus (tus.io) client library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JenSte/aiotus",
    packages=setuptools.find_packages(),
    scripts=["scripts/aiotus-client"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
    ],
    python_requires=">=3.7",
    install_requires=[
        "aiohttp",
        "tenacity",
    ],
    setup_requires=["setuptools_scm"],
    use_scm_version={
        "local_scheme": "dirty-tag"
    },
)
