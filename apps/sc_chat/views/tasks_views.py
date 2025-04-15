#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from rest_framework.views import APIView

from language.language_pack import RET
from sc_chat.tasks import set_ernie_access_token, set_chat_ernie_access_token, test_chat
from sv_voice.tasks import set_ali_access_token
from utils.cst_class import CstResponse


class ErnieAccessToken(APIView):
    authentication_classes = []

    def post(self, request):
        set_ernie_access_token()
        set_chat_ernie_access_token()
        return CstResponse(RET.OK)


class TestChat(APIView):
    authentication_classes = []

    def post(self, request):
        test_chat()
        return CstResponse(RET.OK)


class AliAccessToken(APIView):
    authentication_classes = []

    def post(self, request):
        set_ali_access_token()
        return CstResponse(RET.OK)
