#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json
import logging

from asgiref.sync import sync_to_async
from django.http import StreamingHttpResponse
from rest_framework.decorators import action

from language.language_pack import RET
from utils.async_openai import AsyncOpenAiUtils
from utils.cst_class import CstException
from utils.generics import AsyncGenericAPIView

logger = logging.getLogger(__name__)


class AsyncOpenAiChat(AsyncGenericAPIView):
    """
    openai调用视图 作者：xiaotao 版本号: 文档地址:
    """
    authentication_classes = []

    @action(methods=["post"], detail=False)
    async def post(self, request, *args, **kwargs):
        """
        发起问答
        """
        data = request.data
        try:
            chat_type = int(data["chat_type"])
            model_index = data.get("model_index")
        except ValueError as e:
            raise CstException(RET.DATE_ERROR, "类型异常")
        create_by = data["create_by"]
        msg_list = data["msg_list"]
        max_tokens = data.get("max_tokens") or None
        temperature = data.get("temperature") or 0.6

        if not model_index:
            model_index = chat_type
        op = AsyncOpenAiUtils(create_by, chat_type)
        _ = await sync_to_async(op.set_api_key)()
        completion = await op.acompletion_create(msg_list, model_index, max_tokens, temperature=temperature)  # , stream=True

        async def stream_response():
            for i in completion:
                choices = [dict(h) for h in i.choices]
                for j in choices:
                    j["delta"] = dict(j["delta"])
                rsp = {
                    "choices": choices,
                    "model": i.model,
                }
                # print(i)
                yield json.dumps(rsp) + '\n'

        # application/json; charset=utf-8
        response = StreamingHttpResponse(stream_response(), content_type='text/event-stream; charset=utf-8')
        response['Cache-Control'] = 'no-cache'
        logger.info("----------完成----------")
        return response
