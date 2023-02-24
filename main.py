#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#


import sys

from airbyte_cdk.entrypoint import launch
from source_app_store_amp import SourceAppStoreAmp

if __name__ == "__main__":
    source = SourceAppStoreAmp()
    launch(source, sys.argv[1:])
