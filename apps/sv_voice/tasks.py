#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json

from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.request import CommonRequest
from django_redis import get_redis_connection

from server_chat import settings
from sv_voice.models.digital_human_models import DigitalHumanCustomizedVoice
from utils.ali_sdk import SoundCloneSdk


def set_ali_access_token():
    client = AcsClient(
        settings.ALI_APP_ID,
        settings.ALI_APP_SECRET,
        "cn-shenzhen"
    )

    # 创建request，并设置参数。
    request = CommonRequest()
    request.set_method('POST')
    request.set_domain('nls-meta.cn-shanghai.aliyuncs.com')
    request.set_version('2019-02-28')
    request.set_action_name('CreateToken')

    try:
        resp = client.do_action_with_exception(request)
        redis_conn = get_redis_connection('default')

        jss = json.loads(resp)
        if 'Token' in jss and 'Id' in jss['Token']:
            token = jss['Token']['Id']
            # expireTime = jss['Token']['ExpireTime']
            redis_conn.set("ali_audio", token, ex=60 * 60 * 24 * 10)    # 10天
    except Exception as e:
        pass


def list_customized_voice_task():
    """声音克隆定时任务，一个声音约30分钟左右"""
    query_set = DigitalHumanCustomizedVoice.objects.filter(voice_status=2, is_delete=0).all()
    sdk_obj = SoundCloneSdk()
    for obj in query_set:
        try:
            resp = sdk_obj.list_customized_voice(obj.voice_name)
            status = resp.get("Status")
            model_id = resp.get("ModelId")
            msg = resp.get("Messages")
            if status == "WAIT":
                obj.reason = msg[0]
            elif status == "FAILED":
                obj.reason = msg
                obj.voice_status = 4
            else:
                obj.voice_status = 3
                obj.reason = ""
                obj.model_id = model_id
            obj.save()
        except Exception as e:
            pass

