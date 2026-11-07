#!/usr/bin/env python3
"""
Unziper - Zero 2X Disk Space Archive Extractor
Extracts archives by shrinking the archive in-place or processing chunks,
preventing double disk space consumption during extraction.
"""

import sys

if __name__ == "__main__":
    from unziper.cli import main
    main()
