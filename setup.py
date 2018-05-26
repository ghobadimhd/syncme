#!/usr/bin/env python3

from setuptools import setup

setup(name='syncme',
      version='0.1.3',
      description='Simple rsync wrapper',
      keywords='sample setuptools development',
      author='Mohammad Ghobadi',
      author_email='ghobadimhd@gmail.com',
      url="https://github.com/ghobadimhd/syncme",
      python_requires='==3.5.*',
      install_requires=['pyaml==17.*'],
      py_modules=['syncme'],
      entry_points={
          'console_scripts': [
              'syncme=syncme:main',
          ],
      },
      classifiers=[
          'Development Status :: 3 - Alpha',
          'Intended Audience :: End Users/Desktop',
          'Topic :: Communications :: File Sharing',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3.5',
      ],
)
