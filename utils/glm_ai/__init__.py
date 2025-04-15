#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import os

glm_api_key = os.environ.get("GLM_API_KEY")


api_timeout_seconds = (20, 600)
http_status = 400

model_api_url = os.environ.get(
    "ZHIPUAI_MODEL_API_URL", "https://open.bigmodel.cn/api/paas/v3/model-api"
)
