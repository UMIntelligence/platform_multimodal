#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import abc
import datetime
import json
from http import HTTPStatus

import requests
import websockets
from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
from asgiref.sync import sync_to_async
from dashscope import Generation
from django.db.models import Value, F
from django.db.models.functions import Concat
from django_redis import get_redis_connection
from tencentcloud.common import credential
from tencentcloud.common.exception import TencentCloudSDKException
from tencentcloud.hunyuan.v20230901 import hunyuan_client, models as t_models
from volcengine.maas import MaasService, MaasException

from apps.sc_chat.models.chat_models import CCChatSessionDtl
from apps.sc_chat.utils import deduction_calculation, charges_api
from language.language_pack import RET
from server_chat import settings
from utils import glm_ai
from utils.aes_utils import WsParam, encode_jwt_token
from utils.cst_class import CstException
from utils.exponential_backoff import async_retry_with_exponential_backoff
from utils.generate_number import set_flow
from utils.glm_ai import glm_api
from utils.model_save_data import ModelSaveData
from utils.num_tokens import num_tokens_from_messages
from utils.save_utils import save_session_v2, update_dtl, save_group_chat, update_group_chat
from utils.str_utils import string_to_base64, ali_text_mod_func, url_to_base64


class ChatStrategy(abc.ABC):
    """

    """
    model_filter = ModelSaveData()

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @abc.abstractmethod
    def get_data(self, request, **kwargs):
        pass

    @abc.abstractmethod
    def create(self, data, **kwargs):
        pass

    @abc.abstractmethod
    def data_return(self, response, **kwargs):
        pass


class ChatErnieBotTurbo(ChatStrategy):
    default_model = 'completions'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.redis_conn = get_redis_connection('config')

    def get_data(self, request, **kwargs):
        temperature = request.data.get("temperature") or 0.95

        data = {
            "messages": kwargs["msg_list"],
            "temperature": temperature,
            "user_id": kwargs["create_by"],
            "stream": True,
        }

        # print(data)
        return data

    def create(self, data, **kwargs):
        model = self.kwargs["model"] or self.default_model
        access_token = self.redis_conn.get("baidu_chat_ernie")
        url = settings.EB_HOST + f"rpc/2.0/ai_custom/v1/wenxinworkshop/chat/{model}?access_token={access_token}"
        status = kwargs["status"]

        header = {
            "Content-Type": "application/json"
        }
        try:
            resp = requests.post(url, json=data, headers=header, stream=True)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, data=str(e), status=status)

        return resp

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        model = self.kwargs["model"] or self.default_model
        msg_list = kwargs["msg_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response.iter_lines():
            if event:
                if b"data: " in event:
                    event = event[6:]
                data = json.loads(event)
                # print(data)
                if data.get("error_code"):
                    error_code = data.get("error_code")
                    error_msg = data.get("error_msg")
                    if len(str(error_code)) >= 6:
                        error_code = int(str(error_code)[1:])
                    if error_code == 36003:
                        error_msg = "关联上下文，必须选中关联的一问一答"
                    yield json.dumps({"code": error_code, "msg": error_msg}, ensure_ascii=False) + '\r\n'
                    return

                result = data.get("result", "")
                is_end = data.get("is_end")
                usage = data.get("usage")
                total_tokens = usage.get("total_tokens")    # 总token
                prompt_tokens = usage.get("prompt_tokens")    # 问题token
                save_content += result
                results += result
                if result and is_decode:
                    result = string_to_base64(result)
                resp = {
                    "create_time": create_time,
                    "session_code": session_code if session_code else new_code,
                    "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                    "model": model,
                    "finish_reason": data.get("is_end"),
                    "role": "assistant",
                    "content": result,
                    "msg_code": msg_code,
                    "chat_type": chat_type,
                    "integral": 0,
                    "total_tokens": 0,
                    "completion_tokens": 0,
                    "prompt_tokens": prompt_tokens,
                    "is_mod": 0,
                }

                if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储
                    save_list.append({"role": "assistant", "content": save_content,
                                      "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": prompt_tokens})
                    data = kwargs["data"]
                    session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                        new_code, chat_type, chat_group_code, source,
                                                                        save_list, model=model, data=data)
                    is_save = 1
                    save_content = ""

                if len(save_content) > 50:  # 分片存储
                    await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                        content=Concat(F('content'), Value(save_content)),
                        total_tokens=total_tokens,
                        completion_tokens=total_tokens - prompt_tokens
                    )
                    save_content = ""

                if is_end:      # 结束
                    resp["total_tokens"] = total_tokens
                    resp["completion_tokens"] = total_tokens - prompt_tokens
                    integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                    resp["integral"] = integral
                    try:
                        await sync_to_async(charges_api)(user.user_code, integral)
                    except CstException as e:
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                        await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)
                        return
                    await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)

                yield json.dumps(resp, ensure_ascii=False) + '\r\n'

    async def group_save(self, response, **kwargs):
        model = self.kwargs["model"] or self.default_model
        chat_type = self.kwargs["chat_type"]
        request_data = kwargs["request_data"]
        save_data = kwargs["save_data"]
        group_role_code = save_data["group_role_code"]
        save_list = [save_data]
        session_code = save_data["session_code"]
        create_by = save_data["create_by"]
        is_decode = request_data.get("is_decode")

        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response.iter_lines():
            if event:
                if b"data: " in event:
                    event = event[6:]
                data = json.loads(event)
                if data.get("error_code"):
                    error_code = data.get("error_code")
                    error_msg = data.get("error_msg")
                    if len(str(error_code)) >= 6:
                        error_code = int(str(error_code)[1:])
                    if error_code == 36003:
                        error_msg = "关联上下文，必须选中关联的一问一答"
                    yield json.dumps({"code": error_code, "msg": error_msg}, ensure_ascii=False) + '\r\n'
                    return

                result = data.get("result", "")
                is_end = data.get("is_end")
                usage = data.get("usage")
                total_tokens = usage.get("total_tokens")  # 总token
                prompt_tokens = usage.get("prompt_tokens")  # 问题token
                save_content += result
                results += result
                if result and is_decode:
                    result = string_to_base64(result)
                resp = {
                    "session_code": session_code,
                    "model": model,
                    "finish_reason": None,
                    "role": "assistant",
                    "content": result,
                    "msg_code": msg_code,
                    "chat_type": chat_type,
                    "integral": 0,
                    "total_tokens": 0,
                    "completion_tokens": 0,
                    "prompt_tokens": prompt_tokens,
                    "is_mod": 0,
                }

                if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储
                    save_list.append({"role": "assistant", "content": save_content, "session_code": session_code,
                                      "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": prompt_tokens,
                                      "group_role_code": group_role_code})
                    await sync_to_async(save_group_chat)(save_list, self.model_filter)
                    is_save = 1
                    save_content = ""

                if len(save_content) > 50:  # 分片存储
                    up_data = {"content": results}
                    await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data)
                    save_content = ""

                if is_end:  # 结束
                    up_data = dict()
                    resp["finish_reason"] = "stop"
                    resp["total_tokens"] = total_tokens
                    resp["completion_tokens"] = total_tokens - prompt_tokens
                    integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                    resp["integral"] = integral
                    up_data.update(resp)
                    up_data["content"] = results
                    try:
                        await sync_to_async(charges_api)(create_by, integral)
                    except CstException as e:
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                        await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)
                        return
                    await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)

                yield json.dumps(resp, ensure_ascii=False) + '\r\n'


class ChatSpark(ChatStrategy):
    domain = {
        "v3.1": "generalv3",
        "v2.1": "generalv2",
        "v1.1": "general",
    }
    default_model = 'v3.1'

    def get_data(self, request, **kwargs):
        model = self.kwargs["model"] or self.default_model
        domain = self.domain[model]
        temperature = request.data.get("temperature") or 0.5
        data = {
            "header": {
                "app_id": settings.KD_APP_ID,
                "uid": kwargs["create_by"]
            },
            "parameter": {
                "chat": {
                    "domain": domain,
                    "temperature": temperature,
                    "max_tokens": 2048,
                    "auditing": "default"
                }
            },
            "payload": {
                "message": {
                    "text": kwargs["msg_list"]
                }
            }
        }
        return data

    async def create(self, data, **kwargs):
        model = self.kwargs["model"] or self.default_model
        status = kwargs["status"]
        url = settings.KD_GPT_URL + f"{model}/chat"
        ws_spark = WsParam(settings.KD_APP_ID, settings.KD_API_KEY, settings.KD_API_SECRET, url)
        ws_url = ws_spark.create_url()
        data_to_send = json.dumps(data)
        try:
            websocket = await websockets.connect(ws_url)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, status=status)
        try:
            # 需要发送的数据
            await websocket.send(data_to_send)
        except Exception as e:
            await websocket.close()
            raise CstException(RET.MAX_C_ERR, status=status)
        return websocket

    async def data_return(self, websocket, **kwargs):
        try:
            new_code = set_flow()
            new_group_code = set_flow()
            model = self.kwargs["model"] or self.default_model
            msg_list = kwargs["msg_list"]
            is_decode = kwargs["is_decode"]
            chat_type = kwargs["chat_type"]
            source = kwargs["source"]
            user = kwargs["user"]
            save_list = msg_list[-1:]       # type:list
            chat_group_code = kwargs["chat_group_code"]
            session_code = kwargs["session_code"]
            lod_msg_code = kwargs["lod_msg_code"]
            if not chat_group_code:
                chat_group_code = new_group_code
            create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            msg_code = set_flow()

            save_content = ""
            results = ""

            while True:
                # 等待响应数据
                message = await websocket.recv()
                data = json.loads(message)
                # print(data)
                code = data['header']['code']
                if code != 0:
                    yield json.dumps({"code": code, "msg": data['header']['message']}, ensure_ascii=False) + '\r\n'
                    return
                else:
                    payload = data["payload"]
                    choices = payload["choices"]
                    kd_status = choices["status"]
                    content = choices["text"][0]["content"]
                    # print(payload)
                    save_content += content
                    results += content
                    if content and is_decode:
                        content = string_to_base64(content)

                    resp = {
                        "create_time": create_time,
                        "session_code": session_code if session_code else new_code,
                        "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                        "model": model,
                        "finish_reason": kd_status,
                        "role": "assistant",
                        "content": content,
                        "msg_code": msg_code,
                        "chat_type": chat_type,
                        "integral": 0,
                        "total_tokens": 0,
                        "completion_tokens": 0,
                        "prompt_tokens": 0,
                        "is_mod": 0,
                    }
                    if kd_status == 2:      # 最后一次回答
                        tokens = payload["usage"]["text"]
                        total_tokens = tokens["total_tokens"]
                        prompt_tokens = tokens["prompt_tokens"]
                        resp["total_tokens"] = total_tokens
                        resp["completion_tokens"] = total_tokens - prompt_tokens
                        resp["prompt_tokens"] = prompt_tokens
                        integral = deduction_calculation(chat_type, total_tokens, model)
                        resp["integral"] = integral
                        try:
                            await sync_to_async(charges_api)(user.user_code, integral)
                        except CstException as e:
                            yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                            yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                            await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)
                            return
                        await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        return

                    elif kd_status == 0:  # 第一次一有数据就存储，后面的数据分片存储

                        save_list.append({"role": "assistant", "content": save_content,
                                          "msg_code": msg_code, "finish_reason": "stop"})
                        data = kwargs["data"]
                        session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                            new_code, chat_type, chat_group_code,
                                                                            source, save_list, model=model, data=data)
                        save_content = ""

                    if len(save_content) > 50:  # 分片存储
                        await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                            content=Concat(F('content'), Value(save_content))
                        )
                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'
        finally:
            await websocket.close()

    async def group_save(self, websocket, **kwargs):
        try:
            model = self.kwargs["model"] or self.default_model
            chat_type = self.kwargs["chat_type"]
            request_data = kwargs["request_data"]
            save_data = kwargs["save_data"]
            group_role_code = save_data["group_role_code"]
            save_list = [save_data]
            session_code = save_data["session_code"]
            create_by = save_data["create_by"]
            is_decode = request_data.get("is_decode")

            msg_code = set_flow()

            save_content = ""
            results = ""

            while True:
                # 等待响应数据
                message = await websocket.recv()
                data = json.loads(message)
                # print(data)
                code = data['header']['code']
                if code != 0:
                    yield json.dumps({"code": code, "msg": data['header']['message']}, ensure_ascii=False) + '\r\n'
                    return
                else:
                    payload = data["payload"]
                    choices = payload["choices"]
                    kd_status = choices["status"]
                    content = choices["text"][0]["content"]
                    # print(payload)
                    save_content += content
                    results += content
                    if content and is_decode:
                        content = string_to_base64(content)

                    resp = {
                        "session_code": session_code,
                        "model": model,
                        "finish_reason": None,
                        "role": "assistant",
                        "content": content,
                        "msg_code": msg_code,
                        "chat_type": chat_type,
                        "integral": 0,
                        "total_tokens": 0,
                        "completion_tokens": 0,
                        "prompt_tokens": 0,
                        "is_mod": 0,
                    }

                    if kd_status == 2:      # 最后一次回答
                        up_data = dict()
                        tokens = payload["usage"]["text"]
                        total_tokens = tokens["total_tokens"]
                        prompt_tokens = tokens["prompt_tokens"]
                        resp["total_tokens"] = total_tokens
                        resp["completion_tokens"] = total_tokens - prompt_tokens
                        resp["prompt_tokens"] = prompt_tokens
                        resp["finish_reason"] = "stop"

                        integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                        resp["integral"] = integral
                        up_data.update(resp)
                        up_data["content"] = results
                        try:
                            await sync_to_async(charges_api)(create_by, integral)
                        except CstException as e:
                            yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                            yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                            await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)
                            return
                        await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        return

                    elif kd_status == 0:  # 第一次一有数据就存储，后面的数据分片存储
                        save_list.append({"role": "assistant", "content": save_content, "session_code": session_code,
                                          "msg_code": msg_code, "finish_reason": "stop", "group_role_code": group_role_code})
                        await sync_to_async(save_group_chat)(save_list, self.model_filter)
                        save_content = ""

                    if len(save_content) > 50:  # 分片存储
                        up_data = {"content": results}
                        await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data)
                        save_content = ""

                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'
        finally:
            await websocket.close()


class ChatSparkImage(ChatSpark):
    """看通说话"""
    host = "wss://spark-api.cn-huabei-1.xf-yun.com/"
    default_model = "v2.1"

    def get_data(self, request, **kwargs):
        msg_list = kwargs["msg_list"]
        image_message = msg_list[0]
        try:
            image_url = settings.NETWORK_STATION + image_message["origin_image"]
        except Exception as e:
            raise CstException(RET.DATE_ERROR, "请上传图片")
        image = url_to_base64(image_url)
        image_dict = {
            "role": "user",
            "content": image,
            "content_type": "image"
        }
        msg_list.insert(0, image_dict)
        data = {
            "header": {
                "app_id": settings.KD_APP_ID,
                "uid": kwargs["create_by"]
            },
            "parameter": {
                "chat": {
                    "domain": "general",
                    "temperature": 0.5,
                    "top_k": 4,
                    "max_tokens": 2028,
                    "auditing": "default"
                }
            },
            "payload": {
                "message": {
                    "text": msg_list
                }
            }
        }
        return data

    async def create(self, data, **kwargs):
        model = self.kwargs["model"] or self.default_model
        status = kwargs["status"]
        url = self.host + f"{model}/image"
        ws_spark = WsParam(settings.KD_APP_ID, settings.KD_API_KEY, settings.KD_API_SECRET, url)
        ws_url = ws_spark.create_url()
        data_to_send = json.dumps(data)
        try:
            websocket = await websockets.connect(ws_url)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, status=status)
        try:
            # 需要发送的数据
            await websocket.send(data_to_send)
        except Exception as e:
            await websocket.close()
            raise CstException(RET.MAX_C_ERR, status=status)
        return websocket


class ClaudeChat(ChatStrategy):
    default_model = "claude-v1.3-100k"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.max_tokens_to_sample = 3000

    def get_data(self, request, **kwargs):
        msg_list = kwargs["msg_list"]
        prompt = self._build_prompt(msg_list)
        return {"prompt": prompt}

    @async_retry_with_exponential_backoff
    async def create(self, data, **kwargs):
        model = self.kwargs["model"] or self.default_model
        redis_conn = get_redis_connection('config')
        claude_key = redis_conn.get("CLAUDE_KEY")
        base_url = redis_conn.get("CLAUDE_BASE_URL") or None
        anthropic_obj = Anthropic(api_key=claude_key, base_url=base_url)
        completion = await sync_to_async(anthropic_obj.completions.create)(
            model=model,
            max_tokens_to_sample=self.max_tokens_to_sample,
            prompt=data["prompt"],
            temperature=0.7,
            stream=True
        )
        return completion

    async def data_return(self, response, **kwargs):
        model = self.kwargs["model"] or self.default_model
        new_code = set_flow()
        new_group_code = set_flow()
        msg_list = kwargs["msg_list"]
        send_list = kwargs["send_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prompt_tokens = num_tokens_from_messages(send_list)  # 提问tokens

        msg_code = set_flow()

        save_content = ""
        is_save = 0
        d_save_dict = {"role": "assistant", "content": ""}
        send_list.append(d_save_dict)  # 发送的消息和回答最后一次计算用
        for i in response:
            content = i.completion
            finish_reason = "stop" if i.stop else None
            save_content += content
            d_save_dict["content"] += content
            if content and is_decode:
                content = string_to_base64(content)
            resp = {
                "create_time": create_time,
                "session_code": session_code if session_code else new_code,
                "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                "model": i.model,
                "finish_reason": finish_reason,
                "role": "assistant",
                "content": content,
                "msg_code": msg_code,
                "chat_type": chat_type,
                "integral": 0,
                "total_tokens": 0,
                "completion_tokens": 0,
                "prompt_tokens": prompt_tokens,
                "is_mod": 0,
            }

            if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储

                save_list.append({"role": "assistant", "content": save_content,
                                  "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": prompt_tokens})
                data = kwargs["data"]
                session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                    new_code, chat_type, chat_group_code, source,
                                                                    save_list, model=model, data=data)
                is_save = 1
                save_content = ""

            if len(save_content) > 50:  # 分片存储
                await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                    content=Concat(F('content'), Value(save_content)),
                )
                save_content = ""

            if finish_reason:  # 结束
                results = d_save_dict["content"]
                is_mod, mod_text = ali_text_mod_func(results)  # 检测
                if is_mod == 1:
                    results = mod_text
                total_tokens = num_tokens_from_messages(send_list)
                integral = 0
                resp["is_mod"] = is_mod
                resp["total_tokens"] = total_tokens
                resp["completion_tokens"] = total_tokens - prompt_tokens
                integral = deduction_calculation(chat_type, total_tokens)
                resp["integral"] = integral
                try:
                    await sync_to_async(charges_api)(user.user_code, integral)
                except CstException as e:
                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                    yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                    await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral, is_mod)
                    return
                await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral, is_mod)
            yield json.dumps(resp, ensure_ascii=False) + '\r\n'

    def _build_prompt(self, msg_list):
        prompt = ""
        for msg in msg_list:
            content = msg.get("content")
            role = msg.get("role")
            if role == "assistant":
                prompt += f"{AI_PROMPT}{content}"
            else:
                prompt += f"{HUMAN_PROMPT}{content}"
        prompt += AI_PROMPT
        return prompt


class ChatGLM(ChatStrategy):
    default_model = 'chatglm_turbo'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        glm_key = redis_conn.get("GLM_KEY")
        glm_ai.glm_api_key = glm_key

    def get_data(self, request, **kwargs):
        temperature = request.data.get("temperature") or 0.95

        data = {
            "prompt": kwargs["msg_list"],
            "temperature": temperature,
        }
        # print(data)
        return data

    async def create(self, data, **kwargs):
        completion = glm_api.GLMChatCompletion.create(
            model=self.kwargs["model"],
            prompt=data["prompt"],
            stream=True,
            temperature=data["temperature"],
        )
        return completion

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        model = self.kwargs["model"]
        msg_list = kwargs["msg_list"]
        send_list = kwargs["send_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response.events():
            content = event.data
            if event.code or event.event == "error" or event.event == "interrupted":
                code = event.code
                if not code:
                    code = RET.MAX_C_ERR
                if content == '[1214][prompt 参数非法。请检查文档。]':
                    content = "关联上下文，必须选中关联的一问一答"
                yield json.dumps({"code": code, "msg": content}, ensure_ascii=False) + '\r\n'
                return

            save_content += content
            results += content
            if content and is_decode:
                content = string_to_base64(content)

            resp = {
                "create_time": create_time,
                "session_code": session_code if session_code else new_code,
                "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                "model": model,
                "finish_reason": None,
                "role": "assistant",
                "content": content,
                "msg_code": msg_code,
                "chat_type": chat_type,
                "integral": 0,
                "total_tokens": 0,
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "is_mod": 0,
            }
            # print(event.event)
            if event.event == "finish":     # 结束
                usage = json.loads(event.meta)["usage"]
                total_tokens = usage["total_tokens"]
                prompt_tokens = usage["prompt_tokens"]
                resp["total_tokens"] = total_tokens
                resp["prompt_tokens"] = prompt_tokens
                resp["completion_tokens"] = total_tokens - prompt_tokens
                resp["finish_reason"] = "stop"
                integral = 0    # deduction_calculation(chat_type, total_tokens, model)
                resp["integral"] = integral
                # try:  #
                #     await sync_to_async(charges_api)(user.user_code, integral)
                # except CstException as e:
                #     yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                #     yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                #     await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)
                #     return
                await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)

            if not is_save and save_content:    # 第一次一有数据就存储，后面的数据分片存储

                save_list.append({"role": "assistant", "content": save_content, "msg_code": msg_code, "finish_reason": "stop"})
                data = kwargs["data"]
                session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                    new_code, chat_type, chat_group_code, source,
                                                                    save_list, model=model, data=data)
                is_save = 1
                save_content = ""

            if len(save_content) > 50:  # 分片存储
                await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                    content=Concat(F('content'), Value(save_content)),
                )
                save_content = ""

            yield json.dumps(resp, ensure_ascii=False) + '\r\n'

    async def group_save(self, response, **kwargs):
        model = self.kwargs["model"] or self.default_model
        chat_type = self.kwargs["chat_type"]
        request_data = kwargs["request_data"]
        save_data = kwargs["save_data"]
        group_role_code = save_data["group_role_code"]
        save_list = [save_data]
        session_code = save_data["session_code"]
        create_by = save_data["create_by"]
        is_decode = request_data.get("is_decode")

        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response.events():
            content = event.data
            if event.code or event.event == "error" or event.event == "interrupted":
                code = event.code
                if not code:
                    code = RET.MAX_C_ERR
                if content == '[1214][prompt 参数非法。请检查文档。]':
                    content = "关联上下文，必须选中关联的一问一答"
                yield json.dumps({"code": code, "msg": content}, ensure_ascii=False) + '\r\n'
                return

            save_content += content
            results += content
            if content and is_decode:
                content = string_to_base64(content)

            resp = {
                "session_code": session_code,
                "model": model,
                "finish_reason": None,
                "role": "assistant",
                "content": content,
                "msg_code": msg_code,
                "chat_type": chat_type,
                "integral": 0,
                "total_tokens": 0,
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "is_mod": 0,
            }

            if not is_save and save_content:    # 第一次一有数据就存储，后面的数据分片存储
                save_list.append({"role": "assistant", "content": save_content, "session_code": session_code,
                                  "msg_code": msg_code, "finish_reason": "stop", "group_role_code": group_role_code})
                await sync_to_async(save_group_chat)(save_list, self.model_filter)
                is_save = 1
                save_content = ""

            if len(save_content) > 50:  # 分片存储
                up_data = {"content": results}
                await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data)
                save_content = ""

            if event.event == "finish":     # 结束
                up_data = dict()
                usage = json.loads(event.meta)["usage"]
                total_tokens = usage["total_tokens"]
                prompt_tokens = usage["prompt_tokens"]
                resp["total_tokens"] = total_tokens
                resp["finish_reason"] = "stop"
                resp["completion_tokens"] = total_tokens - prompt_tokens
                resp["prompt_tokens"] = prompt_tokens
                resp["finish_reason"] = "stop"

                integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                resp["integral"] = integral
                up_data.update(resp)
                up_data["content"] = results
                try:
                    await sync_to_async(charges_api)(create_by, integral)
                except CstException as e:
                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                    yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                    await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)
                    return
                await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)

            yield json.dumps(resp, ensure_ascii=False) + '\r\n'


class QwEn(ChatStrategy):
    """通义千问"""
    default_model = 'qwen-turbo'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        self.api_key = redis_conn.get("TYQW_APP_ID")

    def get_data(self, request, **kwargs):
        top_p = request.data.get("top_p") or 0.8
        msg_list = kwargs["msg_list"]
        len_num = len(msg_list)
        if len_num == 1:
            prompt = msg_list[0]["content"]
            history = None
        else:
            prompt = msg_list[len_num - 1]["content"]
            history = self._build_prompt(msg_list)
        data = {
            "prompt": prompt,
            "top_p": top_p,
            "history": history
        }
        return data

    def create(self, data, **kwargs):
        model = self.kwargs["model"] or self.default_model
        responses = Generation.call(
            model=model,
            prompt=data["prompt"],
            history=data["history"],
            api_key=self.api_key,
            stream=True
        )
        return responses

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        model = self.kwargs["model"] or self.default_model
        msg_list = kwargs["msg_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg_code = set_flow()

        is_save = 0
        for event in response:
            if event.status_code == HTTPStatus.OK:
                content = event.output.text
                finish_reason = event.output.finish_reason
                prompt_tokens = event.usage.input_tokens
                total_tokens = event.usage.output_tokens + prompt_tokens
                results = content
                if content and is_decode:
                    results = string_to_base64(content)

                resp = {
                    "create_time": create_time,
                    "session_code": session_code if session_code else new_code,
                    "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                    "model": model,
                    "finish_reason": None,
                    "role": "assistant",
                    "content": results,
                    "msg_code": msg_code,
                    "chat_type": chat_type,
                    "integral": 0,
                    "total_tokens": 0,
                    "completion_tokens": event.usage.output_tokens,
                    "prompt_tokens": prompt_tokens,
                    "is_mod": 0,
                }

                if finish_reason == "stop":  # 结束
                    resp["total_tokens"] = total_tokens
                    resp["completion_tokens"] = event.usage.output_tokens
                    resp["finish_reason"] = finish_reason
                    integral = deduction_calculation(chat_type, total_tokens, model)
                    resp["integral"] = integral
                    try:  #
                        await sync_to_async(charges_api)(user.user_code, integral)
                    except CstException as e:
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                        await update_dtl(session_code, msg_code, content, total_tokens, prompt_tokens, integral)
                        return
                    await update_dtl(session_code, msg_code, content, total_tokens, prompt_tokens, integral)

                if not is_save and content:  # 第一次一有数据就存储，后面的数据分片存储

                    save_list.append({"role": "assistant", "content": content,
                                      "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": prompt_tokens})
                    data = kwargs["data"]
                    session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                        new_code, chat_type, chat_group_code, source,
                                                                        save_list, model=model, data=data)
                    is_save = 1
                # if len(content) > 50:  # 分片存储
                #     await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                #         content=content,
                #     )

                yield json.dumps(resp, ensure_ascii=False) + '\r\n'
            else:
                code, content = event.code, event.message
                yield json.dumps({"code": RET.DATE_ERROR, "msg": content}, ensure_ascii=False) + '\r\n'
                return

    async def group_save(self, response, **kwargs):
        model = self.kwargs["model"] or self.default_model
        chat_type = self.kwargs["chat_type"]
        request_data = kwargs["request_data"]
        save_data = kwargs["save_data"]
        group_role_code = save_data["group_role_code"]
        save_list = [save_data]
        session_code = save_data["session_code"]
        create_by = save_data["create_by"]
        is_decode = request_data.get("is_decode")

        msg_code = set_flow()
        is_save = 0
        for event in response:
            if event.status_code == HTTPStatus.OK:
                content = event.output.text
                finish_reason = event.output.finish_reason
                prompt_tokens = event.usage.input_tokens
                total_tokens = event.usage.output_tokens + prompt_tokens
                results = content
                if content and is_decode:
                    results = string_to_base64(content)

                resp = {
                    "session_code": session_code,
                    "model": model,
                    "finish_reason": finish_reason,
                    "role": "assistant",
                    "content": results,
                    "msg_code": msg_code,
                    "chat_type": chat_type,
                    "integral": 0,
                    "total_tokens": 0,
                    "completion_tokens": 0,
                    "prompt_tokens": prompt_tokens,
                    "is_mod": 0,
                }

                if not is_save and content:  # 第一次一有数据就存储，后面的数据分片存储
                    save_list.append({"role": "assistant", "content": content, "session_code": session_code,
                                      "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": prompt_tokens,
                                      "group_role_code": group_role_code})
                    await sync_to_async(save_group_chat)(save_list, self.model_filter)
                    is_save = 1

                if finish_reason == "stop":  # 结束
                    up_data = dict()
                    is_mod, mod_text = ali_text_mod_func(content)  # 检测
                    if is_mod == 1:
                        content = mod_text
                    resp["is_mod"] = is_mod
                    resp["total_tokens"] = total_tokens
                    resp["completion_tokens"] = event.usage.output_tokens
                    resp["finish_reason"] = finish_reason
                    integral = deduction_calculation(chat_type, total_tokens, model)
                    resp["integral"] = integral
                    up_data.update(resp)
                    up_data["content"] = content
                    try:
                        await sync_to_async(charges_api)(create_by, integral)
                    except CstException as e:
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                        await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)
                        return
                    await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)

                yield json.dumps(resp, ensure_ascii=False) + '\r\n'
            else:
                code, content = event.code, event.message
                yield json.dumps({"code": RET.DATE_ERROR, "msg": content}, ensure_ascii=False) + '\r\n'
                return

    def _build_prompt(self, msg_list):
        history = []
        user_content = ""
        bot_content = ""
        for item in msg_list:
            if item['role'] == "user":
                user_content = item['content']
            elif item['role'] == "assistant":
                bot_content = item['content']
                history.append({"user": user_content, "bot": bot_content})

        return history


class SenseNova(ChatStrategy):
    """商汤"""

    def get_data(self, request, **kwargs):
        temperature = request.data.get("temperature") or 0.8
        msg_list = kwargs["msg_list"]
        create_by = kwargs["create_by"]
        model = self.kwargs["model"] or "nova-ptc-xs-v1"

        data = {
            "model": model,
            "messages": msg_list,
            "stream": True,
            "temperature": temperature,
            "user": create_by,
        }

        return data

    def create(self, data, **kwargs):
        status = kwargs["status"]
        url = "https://api.sensenova.cn/v1/llm/chat-completions"
        headers = {
            "Authorization": encode_jwt_token(settings.ST_APP_ID, settings.ST_APP_SECRET)
        }
        try:
            resp = requests.post(url, json=data, headers=headers, stream=True)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, status=status)

        return resp

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        msg_list = kwargs["msg_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response.iter_lines():
            if event:
                if b"data:" in event:
                    event = event[5:]
                    if b'[DONE]' == event:
                        return
                    event = json.loads(event)
                    status_dict = event.get("status")
                    if status_dict.get("code") != 0:
                        yield json.dumps({"code": status_dict.get("code"), "msg": status_dict.get("message")}, ensure_ascii=False) + '\r\n'
                        return
                    data = event.get("data")
                    choices = data.get("choices")[0]
                    usage = data.get("usage")
                    content = choices.get("delta")
                    finish_reason = choices.get("finish_reason")
                    total_tokens = usage.get("total_tokens")
                    completion_tokens = usage.get("completion_tokens")
                    prompt_tokens = total_tokens - completion_tokens
                    save_content += content
                    results += content
                    if content and is_decode:
                        content = string_to_base64(content)

                    resp = {
                        "create_time": create_time,
                        "session_code": session_code if session_code else new_code,
                        "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                        "model": self.kwargs["model"],
                        "finish_reason": data.get("is_end"),
                        "role": "assistant",
                        "content": content,
                        "msg_code": msg_code,
                        "chat_type": chat_type,
                        "integral": 0,
                        "total_tokens": 0,
                        "completion_tokens": 0,
                        "prompt_tokens": prompt_tokens,
                        "is_mod": 0,
                    }

                    if finish_reason in ["stop", "length", "sensetive"]:  # 结束
                        is_mod, mod_text = ali_text_mod_func(results)  # 检测
                        if is_mod == 1:
                            results = mod_text
                        resp["is_mod"] = is_mod
                        resp["total_tokens"] = total_tokens
                        resp["completion_tokens"] = completion_tokens
                        resp["finish_reason"] = finish_reason
                        integral = deduction_calculation(chat_type, total_tokens)
                        resp["integral"] = integral
                        try:  #
                            await sync_to_async(charges_api)(user.user_code, integral)
                        except CstException as e:
                            yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                            yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                            await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral,
                                             is_mod, finish_reason=finish_reason)
                            return
                        await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral, is_mod,
                                         finish_reason=finish_reason)

                    if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储

                        save_list.append({"role": "assistant", "content": save_content,
                                          "msg_code": msg_code, "finish_reason": "",
                                          "prompt_tokens": prompt_tokens})
                        data = kwargs["data"]
                        session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                            new_code, chat_type, chat_group_code, source,
                                                                            save_list, data=data)
                        is_save = 1
                        save_content = ""

                    if len(save_content) > 50:  # 分片存储
                        await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                            content=Concat(F('content'), Value(save_content)),
                        )
                        save_content = ""

                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'

                else:
                    event = json.loads(event)
                    error_info = event.get("error")
                    yield json.dumps({"code": error_info.get("code"), "msg": error_info.get("message")}, ensure_ascii=False) + '\r\n'
                    return


class BlueprintReading(ChatStrategy):
    def get_data(self, request, **kwargs):
        image_url = request.data.get("image_url")
        if not image_url:
            raise CstException(RET.DATE_ERROR)
        image_url = settings.NETWORK_STATION + image_url
        msg_list = kwargs["msg_list"]
        text = msg_list[-1]["content"]
        history = self._build_prompt(msg_list[:-1])
        image = url_to_base64(image_url)
        data = {
            "image": image,
            "text": text,
            "history": history
        }
        return data

    def create(self, data, **kwargs):
        status = kwargs["status"]
        url = f"http://{settings.ADMIN_HOST}:7863/stream"
        try:
            resp = requests.post(url, json=data, stream=True, timeout=(15, 600))
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, status=status)
        return resp

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        msg_list = kwargs["msg_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        msg_code = set_flow()
        content = ""
        is_save = 0
        for event in response.iter_lines():
            if event:
                if b"data:" in event:
                    event = event[6:]
                    event = json.loads(event)
                    content = event.get("response")
                    finish_reason = event.get("finish_reason")
                    results = content
                    if content and is_decode:
                        results = string_to_base64(content)
                    resp = {
                        "create_time": create_time,
                        "session_code": session_code if session_code else new_code,
                        "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                        "model": self.kwargs["model"],
                        "finish_reason": finish_reason,
                        "role": "assistant",
                        "content": results,
                        "msg_code": msg_code,
                        "chat_type": chat_type,
                        "integral": 0,
                        "total_tokens": 0,
                        "completion_tokens": 0,
                        "prompt_tokens": 0,
                        "is_mod": 0,
                    }

                    if not is_save and content:  # 第一次一有数据就存储，后面的数据分片存储

                        save_list.append({"role": "assistant", "content": content,
                                          "msg_code": msg_code, "finish_reason": "stop"})
                        data = kwargs["data"]
                        session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                            new_code, chat_type, chat_group_code, source,
                                                                            save_list, data=data)
                        is_save = 1
                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'

        is_mod, mod_text = ali_text_mod_func(content)  # 检测
        if is_mod == 1:
            content = mod_text
        await update_dtl(session_code, msg_code, content, 0, 0, 0, is_mod)

    def _build_prompt(self, msg_list):
        history = []
        user_content = ""
        bot_content = ""
        for item in msg_list:
            if item['role'] == "user":
                user_content = item['content']
            elif item['role'] == "assistant":
                bot_content = item['content']
                history.append([user_content, bot_content])

        return history


class QihooChat(ChatStrategy):
    """
    360智脑
    """
    default_model = "360GPT_S2_V9"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        q_key = redis_conn.get("QIHOO_KEY")
        self.headers = {
            "Authorization": f"Bearer {q_key}",
            "Content-Type": "application/json"
        }

    def get_data(self, request, **kwargs):
        model = self.kwargs["model"] or self.default_model
        send_data = {
            "messages": kwargs["msg_list"],
            "model": model,
            "user": kwargs["create_by"],
            "stream": True,
        }
        return send_data

    def create(self, data, **kwargs):
        status = kwargs["status"]
        url = settings.QIHOO_URL + "v1/chat/completions"
        try:
            response = requests.post(url, headers=self.headers, json=data, stream=True)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, status=status)
        if response.status_code != 200:
            message = response.json().get("error").get("message")
            raise CstException(RET.MAX_C_ERR, message, status=status)
        return response

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        model = self.kwargs["model"] or self.default_model
        msg_list = kwargs["msg_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        integral = 0
        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response.iter_lines():
            if b"data: " in event:
                event = event[6:]
                if b'[DONE]' == event:
                    return
                data = json.loads(event)

                result = data.get("choices")[0]["delta"]["content"]
                usage = data.get("usage") or {}
                total_tokens = usage.get("total_tokens") or 0    # 总token
                prompt_tokens = usage.get("prompt_tokens") or 0    # 问题token
                completion_tokens = usage.get("completion_tokens") or 0
                save_content += result
                results += result
                if result and is_decode:
                    result = string_to_base64(result)
                resp = {
                    "create_time": create_time,
                    "session_code": session_code if session_code else new_code,
                    "chat_group_code": chat_group_code if chat_group_code else new_group_code,
                    "model": model,
                    "finish_reason": None,
                    "role": "assistant",
                    "content": result,
                    "msg_code": msg_code,
                    "chat_type": chat_type,
                    "integral": integral,
                    "total_tokens": total_tokens,
                    "completion_tokens": completion_tokens,
                    "prompt_tokens": prompt_tokens,
                    "is_mod": 0,
                }

                if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储

                    save_list.append({"role": "assistant", "content": save_content,
                                      "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": prompt_tokens})
                    data = kwargs["data"]
                    session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                        new_code, chat_type, chat_group_code, source,
                                                                        save_list, model=model, data=data)
                    is_save = 1
                    save_content = ""

                if len(save_content) > 50:  # 分片存储
                    await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                        content=Concat(F('content'), Value(save_content)),
                    )
                    save_content = ""

                if usage:     # 结束
                    resp["finish_reason"] = "stop"
                    integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                    resp["integral"] = integral
                    try:
                        await sync_to_async(charges_api)(user.user_code, integral)
                    except CstException as e:
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                        await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)
                        return
                    await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)

                yield json.dumps(resp, ensure_ascii=False) + '\r\n'

    async def group_save(self, response, **kwargs):
        model = self.kwargs["model"] or self.default_model
        chat_type = self.kwargs["chat_type"]
        request_data = kwargs["request_data"]
        save_data = kwargs["save_data"]
        group_role_code = save_data["group_role_code"]
        save_list = [save_data]
        session_code = save_data["session_code"]
        create_by = save_data["create_by"]
        is_decode = request_data.get("is_decode")

        msg_code = set_flow()
        save_content = ""
        results = ""
        is_save = 0
        for event in response.iter_lines():
            if b"data: " in event:
                event = event[6:]
                if b'[DONE]' == event:
                    return
                data = json.loads(event)

                result = data.get("choices")[0]["delta"]["content"]
                usage = data.get("usage") or {}
                total_tokens = usage.get("total_tokens") or 0    # 总token
                prompt_tokens = usage.get("prompt_tokens") or 0    # 问题token
                completion_tokens = usage.get("completion_tokens") or 0
                save_content += result
                results += result
                if result and is_decode:
                    result = string_to_base64(result)

                resp = {
                    "session_code": session_code,
                    "model": model,
                    "finish_reason": None,
                    "role": "assistant",
                    "content": result,
                    "msg_code": msg_code,
                    "chat_type": chat_type,
                    "integral": 0,
                    "total_tokens": total_tokens,
                    "completion_tokens": completion_tokens,
                    "prompt_tokens": prompt_tokens,
                    "is_mod": 0,
                }

                if not is_save and save_content:    # 第一次一有数据就存储，后面的数据分片存储
                    save_list.append({"role": "assistant", "content": save_content, "session_code": session_code,
                                      "msg_code": msg_code, "finish_reason": "stop", "group_role_code": group_role_code})
                    await sync_to_async(save_group_chat)(save_list, self.model_filter)
                    is_save = 1
                    save_content = ""

                if len(save_content) > 50:  # 分片存储
                    up_data = {"content": results}
                    await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data)
                    save_content = ""

                if usage:     # 结束
                    up_data = dict()

                    resp["finish_reason"] = "stop"
                    integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                    resp["integral"] = integral
                    up_data.update(resp)
                    up_data["content"] = results
                    try:
                        await sync_to_async(charges_api)(create_by, integral)
                    except CstException as e:
                        yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                        yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                        await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral,
                                                               session_code)
                        return
                    await sync_to_async(update_group_chat)(self.model_filter, msg_code, up_data, integral, session_code)

                yield json.dumps(resp, ensure_ascii=False) + '\r\n'


class OpenAiCompletions(ChatStrategy):
    """
    openai
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')

    def get_data(self, request, **kwargs):
        pass

    def create(self, data, **kwargs):
        pass

    async def data_return(self, response, **kwargs):
        pass


class Skylark(ChatStrategy):
    """火山云雀"""

    default_model = "skylark-pro-public"
    url = 'maas-api.ml-platform-cn-beijing.volces.com'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        app_id = redis_conn.get("VG_APP_ID")
        app_secret = redis_conn.get("VG_APP_SECRET")
        self.maas = MaasService(self.url, 'cn-beijing')
        self.maas.set_ak(app_id)
        self.maas.set_sk(app_secret)

    def get_data(self, request, **kwargs):
        model = self.kwargs["model"] or self.default_model
        send_data = {
            "model": {   # skylark-chat   skylark-plus-public
                "name": model,   # skylark2-pro-4k skylark-pro-public   skylark-lite-public
                "version": "1.0",   # use default version if not specified.
            },
            "parameters": {
                "max_new_tokens": 4000,  # 输出文本的最大tokens限制
                "min_new_tokens": 1,  # 输出文本的最小tokens限制
                "temperature": 0.7,  # 用于控制生成文本的随机性和创造性，Temperature值越大随机性越大，取值范围0~1
                "top_p": 0.9,  # 用于控制输出tokens的多样性，TopP值越大输出的tokens类型越丰富，取值范围0~1
                "top_k": 0,  # 选择预测值最大的k个token进行采样，取值范围0-1000，0表示不生效
                "max_prompt_tokens": 4000,  # 最大输入 token 数，如果给出的 prompt 的 token 长度超过此限制，取最后 max_prompt_tokens 个 token 输入模型。
            },
            "messages": kwargs["msg_list"]
        }
        return send_data

    def create(self, data, **kwargs):
        status = kwargs["status"]
        try:
            resp = self.maas.stream_chat(data)
        except MaasException as e:
            raise CstException(RET.MAX_C_ERR, e.message, status=status)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, status=status)
        return resp

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        model = self.kwargs["model"] or self.default_model
        msg_list = kwargs["msg_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        integral = 0
        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response:
            result = event.choice.message.content
            usage = event.usage
            save_content += result
            results += result
            if result and is_decode:
                result = string_to_base64(result)
            resp = {
                "create_time": create_time,
                "session_code": session_code if session_code else new_code,
                "model": model,
                "finish_reason": None,
                "role": "assistant",
                "content": result,
                "msg_code": msg_code,
                "chat_type": chat_type,
                "integral": integral,
                "total_tokens": 0,
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "is_mod": 0,
            }

            if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储

                save_list.append({"role": "assistant", "content": save_content,
                                  "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": 0})
                data = kwargs["data"]
                session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                    new_code, chat_type, chat_group_code, source,
                                                                    save_list, model=model, data=data)
                is_save = 1
                save_content = ""

            if len(save_content) > 50:  # 分片存储
                await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                    content=Concat(F('content'), Value(save_content)),
                )
                save_content = ""

            if usage:  # 结束

                total_tokens = usage.total_tokens
                prompt_tokens = usage.prompt_tokens
                completion_tokens = usage.completion_tokens

                resp["total_tokens"] = total_tokens
                resp["prompt_tokens"] = prompt_tokens
                resp["completion_tokens"] = completion_tokens
                resp["finish_reason"] = "stop"
                integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                resp["integral"] = integral
                try:
                    await sync_to_async(charges_api)(user.user_code, integral)
                except CstException as e:
                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                    yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                    await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)
                    return
                await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)

            yield json.dumps(resp, ensure_ascii=False) + '\r\n'


class HunYuanCompletions(ChatStrategy):

    default_model = "ChatStd"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        ak = redis_conn.get("TXHY_AK")
        sk = redis_conn.get("TXHY_SK")
        cred = credential.Credential(ak, sk)

        self.client = hunyuan_client.HunyuanClient(cred, "ap-guangzhou")

    def get_data(self, request, **kwargs):
        model = self.kwargs["model"] or self.default_model
        msg_list = kwargs["msg_list"]
        new_msg_list = []
        for m in msg_list:
            msg = t_models.Message()
            msg.Role = m["role"]
            msg.Content = m["content"]
            new_msg_list.append(msg)
        if model == self.default_model:
            req = t_models.ChatStdRequest()
            req.Messages = new_msg_list
        else:
            req = t_models.ChatProRequest()
            req.Messages = new_msg_list
        return req

    def create(self, data, **kwargs):
        model = self.kwargs["model"] or self.default_model
        status = kwargs["status"]
        try:
            if model == self.default_model:
                resp = self.client.ChatStd(data)
            else:
                resp = self.client.ChatPro(data)
        except TencentCloudSDKException as e:
            raise CstException(RET.MAX_C_ERR, e.message, status=status)
        return resp

    async def data_return(self, response, **kwargs):
        new_code = set_flow()
        new_group_code = set_flow()
        model = self.kwargs["model"] or self.default_model
        msg_list = kwargs["msg_list"]
        is_decode = kwargs["is_decode"]
        chat_type = kwargs["chat_type"]
        source = kwargs["source"]
        user = kwargs["user"]
        save_list = msg_list[-1:]
        chat_group_code = kwargs["chat_group_code"]
        session_code = kwargs["session_code"]
        lod_msg_code = kwargs["lod_msg_code"]
        if not chat_group_code:
            chat_group_code = new_group_code
        create_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        integral = 0
        msg_code = set_flow()

        save_content = ""
        results = ""
        is_save = 0
        for event in response:
            data = json.loads(event['data'])
            # print(data)
            choice = data['Choices'][0]
            usage = data["Usage"]
            finish_reason = choice.get("FinishReason")
            result = choice['Delta']['Content']
            save_content += result
            results += result
            if result and is_decode:
                result = string_to_base64(result)
            resp = {
                "create_time": create_time,
                "session_code": session_code if session_code else new_code,
                "model": model,
                "finish_reason": None,
                "role": "assistant",
                "content": result,
                "msg_code": msg_code,
                "chat_type": chat_type,
                "integral": integral,
                "total_tokens": 0,
                "completion_tokens": 0,
                "prompt_tokens": 0,
                "is_mod": 0,
            }
            if not is_save and save_content:  # 第一次一有数据就存储，后面的数据分片存储

                save_list.append({"role": "assistant", "content": save_content,
                                  "msg_code": msg_code, "finish_reason": "stop", "prompt_tokens": 0})
                data = kwargs["data"]
                session_code = await sync_to_async(save_session_v2)(lod_msg_code, user.user_code, session_code,
                                                                    new_code, chat_type, chat_group_code, source,
                                                                    save_list, model=model, data=data)
                is_save = 1
                save_content = ""

            if len(save_content) > 50:  # 分片存储
                await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
                    content=Concat(F('content'), Value(save_content)),
                )
                save_content = ""

            if finish_reason == "stop":  # 结束

                total_tokens = usage["TotalTokens"]
                prompt_tokens = usage["PromptTokens"]
                completion_tokens = usage["CompletionTokens"]

                resp["total_tokens"] = total_tokens
                resp["prompt_tokens"] = prompt_tokens
                resp["completion_tokens"] = completion_tokens
                resp["finish_reason"] = "stop"
                integral = deduction_calculation(chat_type, total_tokens, model_name=model)
                resp["integral"] = integral
                try:
                    await sync_to_async(charges_api)(user.user_code, integral)
                except CstException as e:
                    yield json.dumps(resp, ensure_ascii=False) + '\r\n'
                    yield json.dumps({"code": e.code, "msg": e.message}, ensure_ascii=False) + '\r\n'
                    await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)
                    return
                await update_dtl(session_code, msg_code, results, total_tokens, prompt_tokens, integral)

            yield json.dumps(resp, ensure_ascii=False) + '\r\n'

