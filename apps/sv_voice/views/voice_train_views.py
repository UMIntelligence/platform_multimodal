#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
"""
声音训练
"""
import datetime
import json

import requests
from dateutil.relativedelta import relativedelta
from django.db import connections, transaction
from django_redis import get_redis_connection
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from language.language_pack import RET
from server_chat import settings
from sv_voice.models.exchange_models import DigitalHumanActivateCode, DigitalHumanActivateNumber, \
    DigitalHumanActivateConsumeHistory
from sv_voice.models.text_to_speech_models import VtTextToSpeechVoice
from sv_voice.models.voice_train_models import VtVoiceTrainHistory, VtVoiceId
from sv_voice.sqls.voice_train_sqls import TRAIN_HISTORY
from utils import tts_strategy, constants
from utils.cst_class import CstException, CstResponse
from utils.generate_number import set_flow
from utils.model_save_data import ModelSaveData
from utils.redis_lock import LockRequest
from utils.sql_utils import NewSqlMixin, dict_fetchall
from utils.sso_utils import ToOss
from utils.volcengine_utils import TrainStatus


class VolcengineVoiceTrainTask(APIView):
    authentication_classes = []
    status_dict = {
        0: 4,  # 未找到
        1: 2,   # 培训
        2: 3,   # 成功
        3: 4,   # 失败
        4: 5,   # 启用
    }

    def post(self, request):
        """声音过期"""
        # 获取当前时间
        now = datetime.datetime.now()
        expired_voices = VtVoiceTrainHistory.objects.filter(expire_time__lte=now).exclude(voice_status=6).all()

        with transaction.atomic():
            for obj in expired_voices:
                obj.voice_status = 6
                obj.save()
                VtTextToSpeechVoice.objects.filter(engine_code=constants.VG_CODE, voice=obj.voice_id).update(
                    v_status=2
                )

        return CstResponse(RET.OK)

    @LockRequest()
    def put(self, request):
        """训练结果"""
        query_set = VtVoiceTrainHistory.objects.filter(is_delete=0, voice_status__in=[2], voice_type=1).all()
        tts_obj = tts_strategy.VolcengineTTS()
        for obj in query_set:
            status = obj.voice_status
            resp = tts_obj.get_status(obj.voice_id)
            r_status = resp.get("status")
            demo_audio = resp.get("demo_audio")
            url = ""
            if demo_audio:
                oss_obj = ToOss()
                url = oss_obj.main("baidu_tts", img_url=demo_audio, file_extension="wav")
            voice_status = self.status_dict.get(r_status) or 1
            if voice_status != status:
                VtVoiceTrainHistory.objects.filter(train_code=obj.train_code, voice_status=status).update(
                    voice_status=voice_status,
                    demo_audio=url
                )
        return CstResponse(RET.OK)


class VolcengineVoiceTrain(NewSqlMixin, ViewSet):
    """火山声音训练"""

    model_filter = ModelSaveData()

    query_sql = TRAIN_HISTORY
    sort_field = ["a__create_time"]
    where = " and "

    def set_query_sql(self):
        query_sql = self.query_sql
        create_by = self.request.user.user_code
        voice_name = self.request.query_params.get("voice_name")
        voice_status = self.request.query_params.get("voice_status")
        query_sql = query_sql.format(create_by)
        query_sql += f" and a.create_by = '{create_by}'"
        if voice_name:
            query_sql += f" and a.voice_name like '{voice_name}%'"
        if voice_status:
            query_sql += f" and a.voice_status = {voice_status}"

        return query_sql

    def generate_spk_id(self, user_code):
        v_obj = VtVoiceId.objects.filter(voice_status=2, user_code=user_code).first()
        if not v_obj:
            raise CstException(RET.DATE_ERROR, "未找到支付记录，请先支付")
        spk_id = v_obj.voice_id
        if VtVoiceTrainHistory.objects.filter(voice_id=spk_id, voice_type=1).exists():
            raise CstException(RET.DATE_ERROR, "重复提交了")
        return v_obj

    def get_vid_number(self, request):
        user_code = request.user.user_code
        count_number = VtVoiceId.objects.filter(voice_status=2, user_code=user_code).count()
        return CstResponse(RET.OK, data={"count_number": count_number})

    @LockRequest()
    def create(self, request):
        """创建"""
        user_code = request.user.user_code
        data = request.data
        audios = data.get("audios")
        voice_name = data.get("voice_name")
        v_obj = self.generate_spk_id(user_code)

        data["train_code"] = set_flow()

        data["voice_id"] = v_obj.voice_id
        data["create_by"] = user_code

        exclude = ["voice_status", "voice_type"]
        save_data = self.model_filter.get_request_save_data(data, VtVoiceTrainHistory, exclude=exclude)
        save_data["expire_time"] = datetime.datetime.now() - relativedelta(years=-1)
        with transaction.atomic():
            model_obj = VtVoiceTrainHistory.objects.create(**save_data)
            a_obj = DigitalHumanActivateNumber.objects.filter(create_by=user_code, activate_type_id=2, activation_status=1).first()
            if a_obj:
                a_obj.activation_status = 2
                a_obj.save()
                DigitalHumanActivateConsumeHistory.objects.create(
                    create_by=user_code,
                    activate_type_id=2,
                    usage_number=1
                )
            v_obj.voice_status = 3
            v_obj.save()

        try:
            if not all([audios, voice_name]):
                raise CstException(RET.DATE_ERROR)
            for i in audios:
                if not i.get("audio_url"):
                    raise CstException(RET.DATE_ERROR, "提交训练失败，请补充声音数据")

            obj = getattr(tts_strategy, "VolcengineTTS")()

            rsp = obj.voice_train(data)
        except CstException as e:
            model_obj.voice_status = 4
            model_obj.save()
            raise CstException(RET.MAX_C_ERR, "提交训练失败，请前往提交记录中修改数据后重新提交！")
        model_obj.voice_status = 2
        model_obj.save()
        return CstResponse(RET.OK, data={"train_code": model_obj.train_code, "voice_id": model_obj.voice_id})

    @LockRequest()
    def once_again_train(self, request):
        """重新训练"""
        user_code = request.user.user_code
        data = request.data
        train_code = data.get("train_code")
        audios = data.get("audios")
        if not all([train_code, audios]):
            return CstResponse(RET.DATE_ERROR)
        model_obj = VtVoiceTrainHistory.objects.filter(train_code=train_code, create_by=user_code).first()
        if not model_obj:
            return CstResponse(RET.DATE_ERROR, "未找到")
        data["voice_id"] = model_obj.voice_id

        status_message = {
            5: "生效中的状态不能重新训练",
            1: "请先支付",
            2: "请等待训练完成试听效果后再考虑是否重新训练",
            6: "已过期,请联系客服续费",
        }
        msg = status_message.get(model_obj.voice_status)
        if msg:
            return CstResponse(RET.DATE_ERROR, msg)

        obj = getattr(tts_strategy, "VolcengineTTS")()
        rsp = obj.voice_train(data)

        # obj.send_train_queue(data)
        exclude = ["voice_status", "train_code", "voice_id", "expire_time"]
        save_data = self.model_filter.get_request_save_data(data, VtVoiceTrainHistory, exclude=exclude)
        save_data["voice_status"] = 2
        save_data["demo_audio"] = ""
        if not model_obj.expire_time:
            save_data["expire_time"] = datetime.datetime.now() - relativedelta(years=-1)
        for key, value in save_data.items():
            setattr(model_obj, key, value)
        model_obj.save()
        return CstResponse(RET.OK, data={"train_code": model_obj.train_code, "voice_id": model_obj.voice_id})

    @LockRequest()
    def enable_voice(self, reqeust):
        """启用音色"""
        train_code = reqeust.data.get("train_code")
        user = reqeust.user
        user_code = user.user_code
        is_real_name = user.is_real_name
        if not train_code:
            return CstResponse(RET.DATE_ERROR)

        if is_real_name != 2:
            return CstResponse(RET.MAX_C_ERR, "请先实名")

        model_obj = VtVoiceTrainHistory.objects.filter(train_code=train_code, create_by=user_code).first()
        if not model_obj:
            return CstResponse(RET.DATE_ERROR, "未找到")
        if model_obj.voice_status != 3:
            return CstResponse(RET.DATE_ERROR, "只有训练完成才可以启用")

        t_obj = TrainStatus()
        rsp = t_obj.action_tts_train_status([model_obj.voice_id])

        with transaction.atomic():
            model_obj.voice_status = 5
            model_obj.save()

            VtTextToSpeechVoice.objects.create(
                engine_code=constants.VG_CODE,
                voice_code=set_flow(),
                voice=model_obj.voice_id,
                voice_name=model_obj.voice_name,
                speech_url=model_obj.demo_audio,
                voice_type=2,
                create_by=model_obj.create_by
            )
        return CstResponse(RET.OK)


class VoiceIdQuery(APIView):
    """声音id查询"""
    def get(self, request):
        model_obj = VtVoiceId.objects.filter(voice_status=1).first()
        if not model_obj:
            return CstResponse(RET.NO_DATE_ERROR, "声音id已用尽，请联系客服添加")
        return CstResponse(RET.OK)


class VolcengineVoiceTrainPay(APIView):
    """训练支付回调"""
    authentication_classes = []

    @LockRequest()
    def post(self, request):
        user_code = request.data.get("user_code")
        if not user_code:
            return CstResponse(RET.OK, "参数错误")

        model_obj = VtVoiceId.objects.filter(voice_status=1).first()
        if not model_obj:
            return CstResponse(RET.OK, "无声音id")

        model_obj.voice_status = 2
        model_obj.user_code = user_code
        model_obj.save()

        return CstResponse(RET.OK)



