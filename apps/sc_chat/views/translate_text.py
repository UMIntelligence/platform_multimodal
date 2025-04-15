#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import requests
from rest_framework.views import APIView

from language.language_pack import RET
from server_chat import settings
from utils.cst_class import CstResponse


class TextTranslate(APIView):
    authentication_classes = []

    def post(self, request):
        data = request.data
        text = data.get("text")
        dest = data.get("dest") or "en"
        src = data.get("src") or "auto"
        if not text:
            return CstResponse(RET.DATE_ERROR)

        request_data = {
            "text": text,
            "dest": dest,
            "src": src,
        }
        try:
            url = settings.SERVER_OPENAI_URL + "api/server_openai/text_translate"
            result = requests.post(url, json=request_data, timeout=5).json()
        except Exception as e:
            return CstResponse(RET.MAX_C_ERR, data=str(e))

        if result.get("code") != RET.OK:
            return CstResponse(result.get("code"), result.get("msg"))

        return CstResponse(RET.OK, data=result["data"])
