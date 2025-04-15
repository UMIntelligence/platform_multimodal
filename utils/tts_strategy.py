#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import abc
import base64
import json
import time
import uuid
from io import BytesIO

import openai
import requests
from django_redis import get_redis_connection
from openai import OpenAI

from language.language_pack import RET
from sc_chat.utils import charges_api, deduction_calculation
from server_chat import settings
from sv_voice.models.text_to_speech_models import VtTextToSpeechHistory
from sv_voice.models.voice_train_models import VtVoiceTrainHistory
from utils import constants
from utils.aes_utils import SparkTTSRsa
from utils.ali_sdk import VoiceTts
from utils.cst_class import CstException
from utils.exponential_backoff import l_ip
from utils.generate_number import set_flow
from utils.mq_utils import RabbitMqUtil
from utils.sso_utils import ToOss
from utils.str_utils import url_to_base64, get_suffix, base64_to_binary


class TTSStrategy(abc.ABC):
    """

    """
    oss_obj = ToOss()

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @abc.abstractmethod
    def get_data(self, data, **kwargs):
        pass

    @abc.abstractmethod
    def send_data(self, data, **kwargs):
        pass

    @abc.abstractmethod
    def send_queue(self, response, **kwargs):
        pass

    def tts_result(self, message, **kwargs):
        pass

    def charges(self, content):
        user_code = self.kwargs["create_by"]
        engine = self.kwargs["engine"]
        integral = deduction_calculation(engine.engine_code, len(content))
        charges_api(user_code, integral, scene=2)


class OpenAiTTS(TTSStrategy):
    format = "mp3"

    def get_data(self, data, **kwargs):
        voice_obj = self.kwargs["voice_obj"]
        engine = self.kwargs["engine"]
        req_data = {
            "model": engine.model,
            "voice": voice_obj.voice,
            "input": data["content"],
            "response_format": self.format,
            "speed": data.get("speech_rate") or 1.0
        }
        return req_data

    def send_data(self, data, **kwargs):
        action_type = self.kwargs.get("action_type") or 1
        redis_conn = get_redis_connection('config')
        key = "35key_{}".format(l_ip)
        base_key = "api_base_35"
        api_key = redis_conn.get(key)
        api_base = redis_conn.get(base_key) or None

        client = OpenAI(
            api_key=api_key,
            base_url=api_base,
        )
        try:
            response = client.audio.speech.create(
                model=data["model"],
                voice=data["voice"],
                input=data["input"],
                response_format=data.get("response_format") or "mp3",
                speed=data.get("speed") or 1.0,
            )
        except (openai.RateLimitError, openai.AuthenticationError) as e:
            raise CstException(RET.MAX_C_ERR, e.message)
        except openai.APIError as e:
            raise CstException(RET.MAX_C_ERR, e.message)

        with BytesIO() as video_bytes:
            for f_data in response.iter_bytes():
                video_bytes.write(f_data)
            # video_bytes.write(response.read())
            sso_url = self.oss_obj.main("OpenAiTTS", file_con=video_bytes.getvalue(), file_extension="mp3")
            # print(sso_url)
        if action_type == 1:
            self.charges(data["input"])
        return {"speech_url": sso_url, "h_status": 2}

    def send_queue(self, response, **kwargs):
        pass


class AliTTS(TTSStrategy):
    rabbit_mq = RabbitMqUtil()
    url = "https://nls-gateway-cn-shanghai.aliyuncs.com/rest/v1/tts/async"
    format = "wav"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('default')
        token = redis_conn.get("ali_audio")
        self.token = token.decode("utf-8")

    def get_data(self, data, **kwargs):

        voice_obj = self.kwargs["voice_obj"]
        req = {
            "payload": {
                "tts_request": {
                    "voice": voice_obj.voice,
                    "sample_rate": 16000,
                    "format": self.format,
                    "text": data["content"],
                    "speech_rate": data.get("speech_rate") or 0,
                    "pitch_rate": data.get("pitch_rate") or 0,
                    "enable_subtitle": False
                },
                "enable_notify": False
            },
            "context": {
                "device_id": "my_device_id"
            },
            "header": {
                "appkey": settings.A_APP_KEY,
                "token": self.token
            }
        }
        return req

    def send_data(self, data, **kwargs):

        try:
            rsp = requests.post(self.url, json=data).json()
        except Exception as e:
            raise CstException(RET.MAX_C_ERR)
        if rsp.get("status") == 200 and rsp.get("error_code") == 20000000:
            return rsp["data"]
        else:
            raise CstException(RET.MAX_C_ERR, rsp.get("error_message"))

    def send_queue(self, response, **kwargs):
        data = {
            'exchange': constants.EXCHANGE,
            'queue': "tts_query",
            'routing_key': 'tts_result',
            'type': "direct",
            "msg": response
        }
        self.rabbit_mq.send_handle(data)

    def tts_result(self, message, **kwargs):
        task_id = message["task_id"]
        h_code = message["h_code"]
        action_type = self.kwargs.get("action_type") or 1

        self.url += f"?appkey={settings.A_APP_KEY}&task_id={task_id}&token={self.token}"

        for i in range(500):
            if i == 499:
                raise
            try:
                rsp = requests.get(self.url).json()
                print(rsp)
            except Exception as e:
                if i == 6:
                    raise
                time.sleep(2)
                continue
            if rsp.get("status") != 200 and rsp.get("error_code") != 20000000:
                raise
            if rsp.get("error_message") != "SUCCESS":
                time.sleep(2)
                continue
            data = rsp["data"]
            audio_address = data.get("audio_address")
            sso_url = self.oss_obj.main("ali_tts", img_url=audio_address, file_extension=self.format)
            VtTextToSpeechHistory.objects.filter(h_code=h_code).update(
                h_status=2,
                speech_url=sso_url
            )
            if action_type == 1:
                self.charges(message["content"])
            break


class BaiduTTS(TTSStrategy):
    """
    文档 https://cloud.baidu.com/doc/SPEECH/s/ulbxh8rbu
    """
    rabbit_mq = RabbitMqUtil()
    url = "https://aip.baidubce.com"
    format = "wav"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        self.access_token = redis_conn.get("baidu_ernie")

    def get_data(self, data, **kwargs):
        voice_obj = self.kwargs["voice_obj"]
        req = {
            "text": data["content"],
            "format": self.format,
            "voice": voice_obj.voice,
            "lang": "zh",
            "speed": data.get("speech_rate") or 5,  # 取值0-15，默认为5中语速
            "pitch": data.get("pitch_rate") or 5,
            "volume": 8,
            "enable_subtitle": 0
        }
        return req

    def send_data(self, data, **kwargs):
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        url = self.url + f"/rpc/2.0/tts/v1/create?access_token={self.access_token}"
        try:
            rsp = requests.post(url, data=json.dumps(data), headers=headers).json()
        except Exception as e:
            raise CstException(RET.MAX_C_ERR)
        if rsp.get("error_code"):
            raise CstException(RET.MAX_C_ERR, rsp.get("error_msg"))
        return rsp

    def send_queue(self, response, **kwargs):
        data = {
            'exchange': constants.EXCHANGE,
            'queue': "tts_query",
            'routing_key': 'tts_result',
            'type': "direct",
            "msg": response
        }
        self.rabbit_mq.send_handle(data)

    def tts_result(self, message, **kwargs):
        task_id = message["task_id"]
        h_code = message["h_code"]
        action_type = self.kwargs.get("action_type") or 1
        req_data = {
            "task_ids": [task_id]
        }

        url = self.url + f"/rpc/2.0/tts/v1/query?access_token={self.access_token}"

        for i in range(500):
            if i == 499:
                raise
            try:
                rsp = requests.post(url, data=json.dumps(req_data)).json()
                # print(rsp)
            except Exception as e:
                if i == 6:
                    raise
                time.sleep(2)
                continue
            if rsp.get("error_code"):
                raise

            tasks_info = rsp["tasks_info"][0]
            if tasks_info["task_status"] != "Success":
                time.sleep(2)
                continue
            task_result = tasks_info["task_result"]
            speech_url = task_result["speech_url"]
            sso_url = self.oss_obj.main("baidu_tts", img_url=speech_url, file_extension=self.format)
            VtTextToSpeechHistory.objects.filter(h_code=h_code).update(
                h_status=2,
                speech_url=sso_url
            )
            if action_type == 1:
                self.charges(message["content"])
            break


class SparkTTS(TTSStrategy):
    """
    https://www.xfyun.cn/doc/tts/long_text_tts/API.html 文档 .https://console.xfyun.cn/services/long_text
    """
    rabbit_mq = RabbitMqUtil()
    url = "https://api-dx.xf-yun.com"
    format = "mp3"
    app_id = settings.KD_APP_ID

    def get_data(self, data, **kwargs):
        voice_obj = self.kwargs["voice_obj"]
        encode_str = base64.encodebytes(data["content"].encode("UTF8"))
        txt = encode_str.decode()
        req = {
            "header": {
                "app_id": self.app_id,
            },
            "parameter": {
                "dts": {
                    "vcn": voice_obj.voice,
                    "language": "zh",
                    "speed": data.get("speech_rate") or 50,     # 取值范围[0-100]，默认50
                    "volume": 50,
                    "pitch": data.get("pitch_rate") or 50,
                    "rhy": 1,
                    "bgs": 0,
                    "reg": 0,
                    "rdn": 0,
                    "scn": 0,
                    "audio": {
                        "encoding": "lame",     # 下方下载的文件后缀需要保持一致mp3
                        "sample_rate": 16000,
                        "channels": 1,
                        "bit_depth": 16,
                        "frame_size": 0
                    },
                    "pybuf": {
                        "encoding": "utf8",
                        "compress": "raw",
                        "format": "plain"
                    }
                }
            },
            "payload": {
                "text": {
                    "encoding": "utf8",
                    "compress": "raw",
                    "format": "plain",
                    "text": txt
                }
            },
        }
        return req

    def send_data(self, data, **kwargs):
        headers = {'Content-Type': 'application/json'}
        create_path = "/v1/private/dts_create"
        auth_obj = SparkTTSRsa()
        auth_url = auth_obj.assemble_auth_url(create_path)

        try:
            rsp = requests.post(auth_url, data=json.dumps(data), headers=headers).json()
        except Exception as e:
            raise CstException(RET.MAX_C_ERR, "创建声音合成失败")
        header = rsp.get("header")
        if not header:
            raise CstException(RET.MAX_C_ERR, rsp.get("message"))
        if header.get("code") != 0:
            raise CstException(RET.MAX_C_ERR, header.get("message"))
        return header

    def send_queue(self, response, **kwargs):
        data = {
            'exchange': constants.EXCHANGE,
            'queue': "tts_query",
            'routing_key': 'tts_result',
            'type': "direct",
            "msg": response
        }
        self.rabbit_mq.send_handle(data)

    def tts_result(self, message, **kwargs):
        task_id = message["task_id"]
        h_code = message["h_code"]
        action_type = self.kwargs.get("action_type") or 1

        query_path = "/v1/private/dts_query"

        auth_obj = SparkTTSRsa()
        auth_url = auth_obj.assemble_auth_url(query_path)

        headers = {'Content-Type': 'application/json'}
        req_data = {
            "header": {
                "app_id": self.app_id,
                "task_id": task_id
            }
        }

        for i in range(500):
            if i == 499:
                raise
            try:
                rsp = requests.post(url=auth_url, headers=headers, data=json.dumps(req_data)).json()
            except Exception as e:
                if i == 6:
                    raise
                time.sleep(2)
                continue
            header = rsp.get("header")
            if not header:
                raise
            if header.get("code") != 0:
                raise
            task_status = header.get("task_status")
            if task_status == '5':
                audio = rsp.get('payload', {}).get('audio').get('audio')
                # base64解码audio，打印下载链接
                decode_audio = base64.b64decode(audio)
                sso_url = self.oss_obj.main("spark_tts", img_url=decode_audio, file_extension=self.format)
                VtTextToSpeechHistory.objects.filter(h_code=h_code).update(
                    h_status=2,
                    speech_url=sso_url
                )
                if action_type == 1:
                    self.charges(message["content"])
                break
            else:
                time.sleep(2)
                continue


class VolcengineTTS(TTSStrategy):
    """
    火山tts 文档 .https://www.volcengine.com/docs/6561/1167808
    """
    rabbit_mq = RabbitMqUtil()
    appid = settings.VG_TTS_APP_ID
    token = settings.VG_TTS_TOKEN
    host = "https://openspeech.bytedance.com"

    def get_status(self, spk_id):
        url = self.host + "/api/v1/mega_tts/status"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer;" + self.token,
            "Resource-Id": "volc.megatts.voiceclone",
        }
        body = {"appid": self.appid, "speaker_id": spk_id}
        try:
            response = requests.post(url, headers=headers, json=body).json()
        except Exception as e:
            raise CstException(RET.MAX_C_ERR)
        rsp_status = response.get("BaseResp").get("StatusCode")
        if rsp_status != 0:
            raise CstException(RET.THIRD_ERROR, response.get("BaseResp").get("StatusMessage"))
        return response

    def send_train_queue(self, response, **kwargs):
        data = {
            'exchange': constants.EXCHANGE,
            'queue': "tts_train_query",
            'routing_key': 'tts_train_result',
            'type': "direct",
            "msg": response
        }
        self.rabbit_mq.send_handle(data)

    def voice_train(self, data):

        url = self.host + "/api/v1/mega_tts/audio/upload"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer;" + self.token,
            "Resource-Id": "volc.megatts.voiceclone",
        }

        audios = data.get("audios")
        send_audios = []
        for i in audios:
            send_dict = dict()
            send_dict["audio_bytes"] = url_to_base64(settings.NETWORK_STATION + i.get("audio_url"))
            send_dict["audio_format"] = get_suffix(i.get("audio_url"))
            send_audios.append(send_dict)

        send_data = {"appid": self.appid, "speaker_id": data["voice_id"], "audios": send_audios, "source": 2}
        try:
            response = requests.post(url, json=send_data, headers=headers).json()
            # print(response)
        except Exception as e:
            raise CstException(RET.THIRD_ERROR)
        rsp_status = response.get("BaseResp").get("StatusCode")
        if rsp_status != 0:
            raise CstException(RET.THIRD_ERROR, response.get("BaseResp").get("StatusMessage"))
        return response

    def get_data(self, data, **kwargs):
        voice_obj = self.kwargs["voice_obj"]
        request_json = {
            "app": {
                "appid": self.appid,
                "token": "default_token",
                "cluster": data.get("cluster") or "volcano_mega"
            },
            "user": {
                "uid": data["create_by"]
            },
            "audio": {
                "voice_type": voice_obj.voice,
                # "rate": 36000,
                "encoding": "wav",
                "speed_ratio": data.get("speech_rate") or 1.0,   # 语速[0.2,3]
                "volume_ratio": data.get("volume_ratio") or 1.0,    # 音量
                "pitch_ratio": data.get("pitch_rate") or 1.0,    # 音高[0.1, 3]
                "emotion": data.get("emotion") or "",    # 多情感多风格
                "language": data.get("language") or "",    # 多语种多方言
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": data["content"],
                "text_type": "plain",
                "operation": "query",
                "with_frontend": 1,
                "frontend_type": "unitTson",
                "silence_duration": 350

            }
        }
        return request_json

    def send_data(self, data, **kwargs):
        action_type = self.kwargs.get("action_type") or 1
        api_url = self.host + "/api/v1/tts"
        header = {"Authorization": f"Bearer;{self.token}"}
        try:
            resp = requests.post(api_url, json.dumps(data), headers=header).json()
            # print(resp)
        except Exception as e:
            raise CstException(RET.MAX_C_ERR)
        sp_code = resp.get("code")
        if sp_code != 3000:
            raise CstException(RET.THIRD_ERROR, resp.get("message"))
        v_data = resp.get("data")
        binary_data = base64_to_binary(v_data)

        sso_url = self.oss_obj.main("Volcengine", file_con=binary_data, file_extension="wav")
        if action_type == 1:     # 卡密不需要扣
            self.charges(data["request"]["text"])
        return {"speech_url": sso_url, "h_status": 2}

    def send_queue(self, response, **kwargs):
        pass
