#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import datetime
import json
import logging

import requests
from asgiref.sync import sync_to_async
from django.db.models import F, Value
from django.db.models.functions import Concat
from django.http import StreamingHttpResponse
from django_redis import get_redis_connection
from rest_framework.views import APIView

from apps.sc_chat.models.chat_models import CCChatSessionDtl
from apps.sc_chat.utils import check_members, deduction_calculation, charges_api
from language.language_pack import RET
from server_chat import settings
from sv_voice.models.exchange_models import DigitalHumanActivateNumber
from utils import chat_strategy
from utils.ali_sdk import ali_client
from utils.cst_class import CstResponse, CstException
from utils.generate_number import set_flow
from utils.generics import AsyncGenericAPIView
from utils.model_save_data import ModelSaveData
from utils.num_tokens import num_tokens_from_messages
from utils.redis_lock import AsyncLockRequest
from utils.save_utils import save_session_v2, update_dtl
from utils.str_utils import string_to_base64, ali_text_mod_func, get_send_msg

logger = logging.getLogger(__name__)


async def stream_response(result, session_code, chat_group_code, save_list, msg_list, chat_type, create_by, source,
                          is_decode=None, lod_msg_code=None, user=None, **kwargs):
    new_code = set_flow()
    new_group_code = set_flow()
    if not chat_group_code:
        chat_group_code = new_group_code
    create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_list = kwargs["send_list"]
    prompt_tokens = num_tokens_from_messages(send_list)  # 提问tokens

    d_save_dict = {"role": "", "content": ""}
    save_content = ""
    is_save = 0
    msg_code = set_flow()
    send_list.append(d_save_dict)  # 发送的消息和回答最后一次计算用

    for line in result.iter_lines():
        if line:
            data = json.loads(line)
            # print(data)
            choices = data['choices'][0]
            delta = choices['delta']  # extract the text
            finish_reason = choices['finish_reason']  # extract the text
            model = data.get("model")
            for k, v in delta.items():
                if k == "content":
                    save_content += v or ""
                if k in d_save_dict:
                    d_save_dict[k] += v or ""
            content = delta.get("content")
            if content and is_decode:
                content = string_to_base64(content)
            resp = {
                "create_time": create_time,
                "session_code": session_code if session_code else new_code,
                "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                "model": model,
                "finish_reason": finish_reason,
                "role": delta.get("role"),
                "content": content,
                "msg_code": msg_code,
                "chat_type": chat_type,
                "integral": 0,
                "total_tokens": 0,
                "completion_tokens": 0,
                "prompt_tokens": prompt_tokens,
                "is_mod": 0,
            }
            # print(data)

            if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储
                is_save = 1
                save_list.append({"role": "assistant", "content": save_content,
                                  "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": prompt_tokens})
                r_data = kwargs["data"]
                session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                    new_code, chat_type, chat_group_code, source,
                                                                    save_list, model, data=r_data)
                save_content = ""

            if len(save_content) > 50:  # 分片存储
                await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                    content=Concat(F('content'), Value(save_content)),
                )
                save_content = ""
            if finish_reason:       # 结束
                content = d_save_dict["content"]
                is_mod, mod_text = ali_text_mod_func(content)   # 检测
                if is_mod == 1:
                    content = mod_text
                total_tokens = num_tokens_from_messages(send_list)
                resp["is_mod"] = is_mod
                resp["total_tokens"] = total_tokens
                resp["completion_tokens"] = total_tokens - prompt_tokens
                integral = deduction_calculation(chat_type, total_tokens)
                resp["integral"] = integral
                try:  #
                    await sync_to_async(charges_api)(user.user_code, integral)
                except CstException as e:
                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                    yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                    await update_dtl(session_code, msg_code, content, total_tokens, prompt_tokens, integral, is_mod,
                                     role=d_save_dict["role"], finish_reason=finish_reason)
                    return
                await update_dtl(session_code, msg_code, content, total_tokens, prompt_tokens, integral, is_mod,
                                 role=d_save_dict["role"], finish_reason=finish_reason)
            yield json.dumps(resp, ensure_ascii=False) + '\r\n'


class AsyncChatView(AsyncGenericAPIView):
    """
    gpt会话视图 作者：xiaotao 版本号: 文档地址:
    """

    @AsyncLockRequest()
    async def post(self, request):
        user = request.user
        data = request.data
        source = user.source
        create_by = user.user_code
        chat_type = str(data.get("chat_type"))  # 类型0:gpt3.5, 1:gpt4.0
        model_index = data.get("model_index")  # 模型类型0:gpt3.5, 1:gpt4.0，2：pt3.5
        temperature = data.get("temperature") or 0.8  #
        session_code = data.get("session_code")
        chat_group_code = data.get("chat_group_code")
        msg_list = data.get("msg_list")
        is_decode = data.get("is_decode")
        lod_msg_code = data.get("msg_code")
        stream = True
        status = 400

        if chat_type not in ["0", "1"] or not msg_list:
            return CstResponse(RET.DATE_ERROR, status=status)
        if model_index:
            try:
                model_index = int(model_index)
            except ValueError as e:
                return CstResponse(RET.DATE_ERROR, status=status)

        try:
            msg_list = json.loads(msg_list)
        except Exception as e:
            return CstResponse(RET.DATE_ERROR, status=status)

        _ = check_members(create_by, status=status)

        ali_str = ",".join([i["content"] for i in msg_list if i["role"] == "user"])
        if len(ali_str) < 600:
            _ = ali_client.ali_text_mod(json.dumps({"content": ali_str}, ensure_ascii=False), status=status)
        logger.info(f"""{datetime.datetime.now()}--{str(data)}""")

        send_list = get_send_msg(msg_list)
        max_tokens = None
        request_data = {
            "msg_list": send_list,
            "chat_type": chat_type,
            "model_index": model_index,
            "max_tokens": max_tokens,
            "create_by": create_by,
            "temperature": temperature,
            "stream": stream
        }

        try:
            if chat_type == "0":
                base_key = "api_base_35"
                redis_conn = get_redis_connection('config')
                api_base = redis_conn.get(base_key) or None
                if api_base:
                    url = settings.CALLBACK + "api/chat/async_chat_send"
                else:
                    url = settings.SERVER_OPENAI_URL + "api/server_openai/async_chat_send"
            else:
                url = settings.CALLBACK + "api/chat/async_chat_send"
            result = requests.post(url, json=request_data, stream=stream, timeout=(30, 600))
            # print("-----------------")
        except Exception as e:
            return CstResponse(RET.MAX_C_ERR, data=str(e), status=status)

        status_code = result.status_code
        if status_code != 200:
            try:
                result = result.json()
            except Exception as e:
                logger.error(f"""{datetime.datetime.now()}--{str(e)}""")

                return CstResponse(RET.FREQUENTLY, status=status)
            logger.error(f"""{datetime.datetime.now()}--{str(result)}--{status_code}""")
            if 400 <= status_code <= 499:  # openai错误数据结构
                return CstResponse(RET.DATE_ERROR, result.get("msg"), status=status)
            return CstResponse(RET.DATE_ERROR, result.get("msg"), status=status)
        logger.info(f"""{datetime.datetime.now()}--{"成功"}""")

        save_list = msg_list[-1:]

        response = StreamingHttpResponse(
            stream_response(result, session_code, chat_group_code, save_list, msg_list, chat_type, create_by, source,
                            is_decode, lod_msg_code, user=user, data=data, send_list=send_list),
            content_type='text/event-stream; charset=utf-8')  # text/event-stream; charset=utf-8  application/json
        response['Cache-Control'] = 'no-cache'
        print("-------11111")
        return response


class AsyncChatCompletion(AsyncGenericAPIView):
    """
    会话完成视图 作者：xiaotao 版本号: 文档地址:
    """
    chat_type_map = {
        "4": "ChatErnieBotTurbo",       # 文心一言
        "5": "ChatSpark",               # 科大讯飞
        "1002": "ChatSparkImage",       # 科大讯飞图片理解
        "7": "ClaudeChat",               # Claude
        "8": "ChatGLM",               # GLM
        "10": "QwEn",               # 千问
        "11": "SenseNova",               # 商汤
        "12": "QihooChat",               # 360智脑
        "-5": "QihooChat",               # 360智脑
        "1000": "Skylark",               # 火山云雀
        "1001": "HunYuanCompletions",    # 混元
        "-2": "BlueprintReading",               # 识图
        "-3": "ChatGLM",  # GLM
        "-4": "ChatGLM",  # GLM
    }

    @AsyncLockRequest()
    async def post(self, request):
        user = request.user
        data = request.data
        source = user.source
        create_by = user.user_code
        chat_type = str(data.get("chat_type"))  # 类型4:文心一言bot turbo 5:科大讯飞
        session_code = data.get("session_code")
        chat_group_code = data.get("chat_group_code")
        msg_list = data.get("msg_list")  # 提问
        is_decode = data.get("is_decode")
        lod_msg_code = data.get("msg_code")  # 详情id
        model = data.get("model", "")  # 模型
        action_type = data.get("action_type") or 1    # 类型1算力，2卡密
        status = 400

        if chat_type not in self.chat_type_map.keys() or not msg_list:
            return CstResponse(RET.DATE_ERROR, status=status)

        try:
            msg_list = json.loads(msg_list)
        except Exception as e:
            return CstResponse(RET.DATE_ERROR, status=status)

        if action_type == 1:
            _ = check_members(create_by, status=status)
        else:
            if not await DigitalHumanActivateNumber.objects.filter(create_by=create_by, activate_type_id=4, activate_status=1).aexists():
                return CstResponse(RET.NO_NUMBER, "无可用次数，请先兑换卡密", status=status)

        ali_str = ",".join([i["content"] for i in msg_list if i["role"] == "user"])
        if len(ali_str) < 600:
            _ = ali_client.ali_text_mod(json.dumps({"content": ali_str}, ensure_ascii=False), status=status)
        logger.info(f"""{datetime.datetime.now()}--{str(data)}""")

        obj = getattr(chat_strategy, self.chat_type_map[chat_type])(model=model)

        send_list = get_send_msg(msg_list)
        request_data = obj.get_data(request, msg_list=send_list, create_by=create_by)
        if chat_type in ["5", "7", "8", "1002", "-3", "-4"]:
            resp = await obj.create(request_data, status=status)
        else:
            resp = await sync_to_async(obj.create)(request_data, status=status)

        response = StreamingHttpResponse(obj.data_return(
            resp, msg_list=msg_list, session_code=session_code, chat_group_code=chat_group_code, user=user,
            source=source, data=data, send_list=send_list,
            lod_msg_code=lod_msg_code, is_decode=is_decode, chat_type=chat_type, status=status
        ), content_type='text/event-stream; charset=utf-8')
        response['Cache-Control'] = 'no-cache'
        print("-------11111")
        return response


class UpdateSessionDtl(APIView):
    model_filter = ModelSaveData()

    def put(self, request):
        data = request.data
        msg_code = data.get("msg_code")
        if not msg_code:
            return CstResponse(RET.DATE_ERROR)

        exclude = ["id", "msg_code", "session_code"]
        save_data = self.model_filter.get_request_save_data(data, CCChatSessionDtl, exclude=exclude)
        CCChatSessionDtl.objects.filter(msg_code=msg_code).update(**save_data)
        return CstResponse(RET.OK)