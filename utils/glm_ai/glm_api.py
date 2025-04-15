#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import posixpath

import requests

from language.language_pack import RET
from utils import glm_ai
from utils.cst_class import CstException
from utils.glm_ai import glm_jwt_token
from utils.glm_ai.glm_sse_client import SSEClient


def glm_stream(api_url, token, params, timeout):
    try:
        resp = requests.post(
            api_url,
            stream=True,
            headers={"Authorization": token},
            json=params,
            timeout=timeout,
        )
        if requests.codes.ok != resp.status_code:
            raise CstException(RET.MAX_C_ERR, status=glm_ai.http_status)
        return resp
    except Exception as e:
        raise CstException(RET.MAX_C_ERR, status=glm_ai.http_status)


class InvokeType:
    SYNC = "invoke"
    ASYNC = "async-invoke"
    SSE = "sse-invoke"


class GLMChatCompletion:

    @classmethod
    def create(cls, **kwargs):
        url = cls._build_api_url(kwargs, InvokeType.SSE)
        completion = glm_stream(url, cls._generate_token(), kwargs, glm_ai.api_timeout_seconds)
        return SSEClient(completion)

    @staticmethod
    def _build_api_url(kwargs, *path):
        if kwargs:
            if "model" not in kwargs:
                raise CstException(RET.MODEL_ERR, status=glm_ai.http_status)
            model = kwargs.pop("model")
        else:
            model = "-"

        return posixpath.join(glm_ai.model_api_url, model, *path)

    @staticmethod
    def _generate_token():
        if not glm_ai.glm_api_key:
            raise CstException(RET.MAX_C_ERR, message="api_key not provided, you could provide it with `shell: export API_KEY=xxx` or `code: zhipuai.api_key=xxx`", status=glm_ai.http_status)

        return glm_jwt_token.generate_token(glm_ai.glm_api_key)
