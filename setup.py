import setuptools
with open("README.md", "r") as fh:
    long_description = fh.read()
setuptools.setup(
    name='acnportal',
    version='0.1.4',
    author='Zachary Lee',
    author_email="zlee@caltech.edu",
    url='https://github.com/mcr229/acnportal',
    description="A package of tools for large-scale EV charging research.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    package_data={'': ['LICENSE.txt', 'THANKS.txt']},
    include_package_data=True,
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Programming Language :: Python',
        'License :: OSI Approved :: BSD License',
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'numpy',
        'pandas',
        'matplotlib',
        'requests',
        'pytz'
    ]
)
