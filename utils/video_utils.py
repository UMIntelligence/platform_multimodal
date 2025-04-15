#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import os
import subprocess
import tempfile

import requests
from _decimal import Decimal

from server_chat.settings import BASE_DIR


def get_video_length(url):
    r = requests.get(url, stream=True)
    if r.status_code == 200:
        dir_s = os.path.join(BASE_DIR, 'static')
        with tempfile.NamedTemporaryFile(dir=dir_s, delete=False) as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)

        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", f.name], capture_output=True, text=True)
        duration = Decimal(result.stdout) / Decimal(60)
        os.unlink(f.name)
        return str(duration)
    else:
        # print("Failed to download video")
        return 1
