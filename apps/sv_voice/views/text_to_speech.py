#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI

"""
文本转语音
"""
import json
import operator
from functools import reduce

from django.db import connections
from django.db.models import Q
from django.forms import model_to_dict
from rest_framework.views import APIView

from language.language_pack import RET
from sc_chat.utils import check_members
from sv_voice.models.exchange_models import DigitalHumanActivateNumber
from sv_voice.models.text_to_speech_models import VtTextToSpeechHistory, VtTextToSpeechEngine, VtTextToSpeechVoice
from sv_voice.sqls import text_to_speech_sqls
from utils import constants, tts_strategy
from utils.ali_sdk import ali_client
from utils.cst_class import CstResponse
from utils.generate_number import set_flow
from utils.generics import TyModelViewSet
from utils.model_save_data import ModelSaveData
from utils.sql_utils import NewSqlMixin, dict_fetchall


class GetSpeechEngine(APIView):
    """
    文本转语音引擎 作者： 版本号: 文档地址:
    """

    def get(self, request):
        scene_type = request.query_params.get("scene_type") or ""
        rows = VtTextToSpeechEngine.objects.filter(scene_type=scene_type).values("engine_code", "engine_name")
        return CstResponse(RET.OK, data=rows)


class GetSpeechVoice(APIView):
    """
    文本转语音色 作者： 版本号: 文档地址:
    """

    def get(self, request):
        user_code = request.user.user_code
        s_list = []
        engine_code = request.query_params.get("engine_code")
        voice_type = request.query_params.get("voice_type") or 1
        language = request.query_params.get("language")
        gender = request.query_params.get("gender")

        s_list.append(Q(("engine_code", engine_code)))
        s_list.append(Q(("voice_type", voice_type)))
        s_list.append(Q(("is_delete", 0)))
        s_list.append(Q(("v_status", 1)))
        if language:
            s_list.append(Q(language__contains=language))
        if int(voice_type) != 1:
            s_list.append(Q(("create_by", user_code)))
        if gender:
            s_list.append(Q(("gender", gender)))

        rows = VtTextToSpeechVoice.objects.filter(reduce(operator.and_, s_list)).values(
            "voice_code", "voice", "voice_name", "voice_logo", "speech_url", "language", "desc", "gender", "engine_code"
        )
        return CstResponse(RET.OK, data=rows)


class TextToSpeechResult(APIView):
    """
    文本转语音结果 作者： 版本号: 文档地址:
    """
    def get(self, request):
        h_code = request.query_params.get("h_code")
        rows = VtTextToSpeechHistory.objects.filter(h_code=h_code).values(
            "h_status", "speech_url"
        )
        if rows:
            rows = rows[0]
        return CstResponse(RET.OK, data=rows)


class TextToSpeech(NewSqlMixin, TyModelViewSet):
    """
    文本转语音 作者： 版本号: 文档地址:
    """
    model_filter = ModelSaveData()
    query_sql = text_to_speech_sqls.SpeechList
    sort_field = ["create_time"]
    where = " and "
    lookup_field = "h_code"
    queryset = VtTextToSpeechHistory.objects.filter(is_delete=0)

    def set_query_sql(self):
        user_code = self.request.user.user_code
        self.query_sql += f" and create_by = '{user_code}'"
        title = self.request.query_params.get("title")
        engine_code = self.request.query_params.get("engine_code")
        if engine_code:
            self.query_sql += f" and engine_code='{engine_code}' "
        if title:
            self.query_sql += f" and title like '{title}%'"
        return self.query_sql

    def retrieve(self, request, *args, **kwargs):
        h_code = self.kwargs[self.lookup_url_kwarg or self.lookup_field]
        with connections["default"].cursor() as cursor:
            cursor.execute(text_to_speech_sqls.SpeechDtl, [h_code])
            rows = dict_fetchall(cursor)
        if not rows:
            return CstResponse(RET.NOT_FOUND)
        return CstResponse(RET.OK, data=rows[0])

    def create(self, request, *args, **kwargs):
        data = request.data
        user_code = request.user.user_code
        content = data.get("content")
        engine_code = data.get("engine_code")
        voice_code = data.get("voice_code")
        action_type = data.get("action_type") or 1
        if not all([content, engine_code, voice_code]):
            return CstResponse(RET.DATE_ERROR)

        engine = VtTextToSpeechEngine.objects.filter(engine_code=engine_code).first()
        if not engine:
            return CstResponse(RET.DATE_ERROR, "引擎错误")

        voice_obj = VtTextToSpeechVoice.objects.filter(engine_code=engine_code, voice_code=voice_code).first()
        if not voice_obj:
            return CstResponse(RET.DATE_ERROR, "声音错误")
        if voice_obj.v_status != 1:
            return CstResponse(RET.DATE_ERROR, "声音已过期,请联系客服续费")
        if action_type == 1:
            _ = check_members(user_code, scene=constants.TEXT_SCENE, num=len(content), bus_type=engine.engine_code)
        else:
            if not DigitalHumanActivateNumber.objects.filter(create_by=user_code, activate_type_id=4, activate_status=1).exists():
                return CstResponse(RET.NO_NUMBER, "无可用次数，请先兑换卡密")

        if len(content) < 600:
            _ = ali_client.ali_text_mod(json.dumps({"content": content}, ensure_ascii=False))

        h_code = set_flow()
        data["h_code"] = h_code
        data["title"] = content[:15] + "..."
        data["create_by"] = user_code
        data["action_type"] = action_type
        obj = getattr(tts_strategy, engine.class_name)(create_by=user_code, engine=engine, voice_obj=voice_obj, action_type=action_type)

        request_data = obj.get_data(data)

        result = obj.send_data(request_data)

        data.update(result)

        obj.send_queue(data)

        save_data = self.model_filter.get_request_save_data(data, VtTextToSpeechHistory)
        model_obj = VtTextToSpeechHistory.objects.create(**save_data)

        return CstResponse(RET.OK, data=model_to_dict(model_obj))
