# -*- coding: utf-8 -*-
"""`Kotlin Sphinx domain` on `Github`_.
.. _github: https://github.com/nextgis/kotlin_sphinx
"""
from setuptools import setup

setup(
    name='kotlin_sphinx',
    version="0.1",
    url='https://github.com/nextgis/kotlin_sphinx',
    license='GPLv2',
    author='Dmitry Baryshnikov',
    author_email='dmitry.baryshnikov@nextgis.com',
    description='Kotlin support for Sphinx.',
    long_description=open('README.md').read(),
    zip_safe=False,
    packages=['kotlin_domain'],
    package_data={},
    entry_points={
        'console_scripts': [
            'kotlinsphinx=kotlin_domain.generator:main',
        ],
    },
    include_package_data=True,
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GPL v2 License',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        'Topic :: Documentation',
        'Topic :: Software Development :: Documentation',
    ],
    install_requires=[
        'sphinx'
    ]
)
