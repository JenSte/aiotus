import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aiotus",
    version="0.1.8",
    author="Jens Steinhauser",
    author_email="jens.steinhauser@gmail.com",
    description="Asynchronous tus (tus.io) client library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/JenSte/aiotus",
    project_urls={"Documentation": "https://aiotus.readthedocs.io"},
    license="Apache 2",
    packages=setuptools.find_packages(),
    package_data={"aiotus": ["py.typed"]},
    include_package_data=True,
    zip_safe=False,
    entry_points={
        "console_scripts": [
            "aiotus-upload=aiotus.entrypoint:aiotus_upload",
            "aiotus-metadata=aiotus.entrypoint:aiotus_metadata",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Development Status :: 4 - Beta",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        "Typing :: Typed",
    ],
    python_requires=">=3.7",
    install_requires=["aiohttp", "tenacity"],
    setup_requires=["setuptools_scm"],
    use_scm_version={"local_scheme": "dirty-tag"},
)
