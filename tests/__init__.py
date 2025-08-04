"""Test suite for gitlab-fsspec.

Most tests use the public test repository at:
https://gitlab.com/gitlab-filesystem-test-repos/public

Repository structure:
.
├── data
│   ├── config.xml
│   ├── data.csv
│   └── sample.json
├── docs
│   ├── README_internal.md
│   └── sample.txt
├── empty
├── media
│   ├── image_info.txt
│   └── tiny.png
├── nested
│   ├── deep
│   │   └── very
│   │       └── far
│   │           └── deep_file.txt
│   └── intermediate.md
├── README.md
└── scripts
    ├── config.sh
    ├── example.py
    └── package.json

This repository contains a structured directory tree with various file types
and nested directories specifically designed for testing filesystem operations.
"""
