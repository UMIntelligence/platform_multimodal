#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json
import math
import os
import tempfile
from io import BytesIO

import cv2
from django.db import connections, transaction
from django.forms import model_to_dict
from django_redis import get_redis_connection
from pydub import AudioSegment
from rest_framework.decorators import action
from rest_framework.viewsets import ModelViewSet, ViewSet
from rest_framework_extensions.cache.decorators import cache_response

from language.language_pack import RET
from server_chat.settings import BASE_DIR
from sv_voice.filter_utils import DigitalHumanCloneFilter
from sv_voice.models.digital_human_models import DigitalHumanFile, DigitalHumanLiveVideo, DigitalHumanLiveVideoDtl, \
    DigitalHumanCustomizedVoice, DigitalHumanVoiceGenerateHistory, DigitalHumanProject
from sv_voice.models.exchange_models import DigitalHumanActivateNumber, DigitalHumanActivateConsumeHistory
from sv_voice.models.text_to_speech_models import VtTextToSpeechVoice, VtTextToSpeechEngine
from sv_voice.serializers.digital_human_serializers import DigitalHumanExperienceSerializer, DigitalHumanFileSerializer, \
    DigitalHumanCloneSerializer, CustomizedVoiceSerializer, DigitalHumanProjectSerializer, \
    ShortVideoDigitalHumanCloneSerializer
from sv_voice.sqls import digital_human_sqls
from sv_voice.tasks import list_customized_voice_task
from utils.ali_sdk import SoundCloneSdk, VoiceTts
from utils.cst_class import CstResponse, CstException
from utils.generate_number import set_flow
from utils.generics import TyModelViewSet
from utils.model_save_data import ModelSaveData
from utils.redis_lock import LockRequest
from utils.shared_method import CstPageNumberPagination
from utils.sql_utils import NewSqlMixin, dict_fetchall
from utils.sso_utils import ToOss
from utils.tts_strategy import VolcengineTTS

cache_time = 60 * 60 * 2


class DigitalHumanExperienceView(ModelViewSet):
    """

    """
    authentication_classes = []
    serializer_class = DigitalHumanExperienceSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return CstResponse(RET.OK, data=serializer.data)


class DigitalHumanFileViews(NewSqlMixin, ModelViewSet):
    """
    数字人文件收集 作者：xiaotao 版本号: 文档地址:
    """
    queryset = DigitalHumanFile.objects.filter(is_delete=0)
    serializer_class = DigitalHumanFileSerializer
    sort_field = ["create_time"]
    sort_type = "desc"
    main_table = "a"
    where = " and "
    query_sql = digital_human_sqls.DigitalHumanFileSql
    lookup_field = "file_code"

    def set_query_sql(self):
        query_sql = self.query_sql
        create_by = self.request.user.user_code
        if create_by:
            query_sql += f" and create_by= '{create_by}'"

        return query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def perform_destroy(self, instance):
        instance.is_delete = 1
        instance.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return CstResponse(RET.OK, data=serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return CstResponse(RET.OK)


class MyDigitalHumanView(NewSqlMixin, ViewSet):
    """
    我的数字人
    """
    sort_field = ["create_time"]
    sort_type = "desc"
    where = " and "
    query_sql = digital_human_sqls.MyDigitalHumanSql

    def set_query_sql(self):
        query_sql = self.query_sql
        create_by = self.request.user.user_code
        live_type = self.request.query_params.get("live_type")
        live_name = self.request.query_params.get("live_name")
        make_status = self.request.query_params.get("make_status")
        query_sql += f" and create_by= '{create_by}'"
        if live_type:
            query_sql = f" select * from ({query_sql}) as a where live_type={live_type}"
        if live_name:
            query_sql += f" and live_name='{live_name}'"
        if make_status:
            query_sql += f" and make_status={make_status}"

        return query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})


class DigitalHumanProjectList(NewSqlMixin, ViewSet):
    """
    口播视频项目列表
    """
    sort_field = ["b__create_time"]
    sort_type = "desc"
    where = " and "
    query_sql = digital_human_sqls.DigitalHumanProjectSql

    def set_query_sql(self):
        query_sql = self.query_sql
        create_by = self.request.user.user_code
        project_status = self.request.query_params.get("project_status")
        query_sql += f" and b.create_by= '{create_by}'"
        if project_status:
            query_sql += f" and b.project_status= {project_status}"

        return query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})


class MyLiveVideoView(NewSqlMixin, ViewSet):
    """
    我的口播视频列表
    """
    sort_field = ["b__create_time"]
    sort_type = "desc"
    where = " and "
    query_sql = digital_human_sqls.MyLiveVideoSql

    def set_query_sql(self):
        query_sql = self.query_sql
        create_by = self.request.user.user_code
        make_status = self.request.query_params.get("make_status")
        query_sql += f" and b.create_by= '{create_by}'"
        if make_status:
            query_sql += f" and c.make_status= {make_status}"

        return query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def update(self, request, *args, **kwargs):
        live_dtl_code = request.data.get("live_dtl_code")
        obj = DigitalHumanLiveVideoDtl.objects.filter(live_dtl_code=live_dtl_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "未找到")
        if obj.make_status != 4:
            return CstResponse(RET.DATE_ERROR, "失败的才可以重新制作")
        obj.make_status = 1
        obj.save()
        return CstResponse(RET.OK)


class DigitalHumanClone(TyModelViewSet):
    """
    数字人形象 作者：xiaotao 版本号: 文档地址:
    """
    queryset = DigitalHumanLiveVideo.objects.filter(is_delete=0)
    serializer_class = DigitalHumanCloneSerializer
    lookup_field = "live_code"
    model_filter = ModelSaveData()
    pagination_class = CstPageNumberPagination
    filter_backends = [DigitalHumanCloneFilter]


class ShortVideoDigitalHumanClone(TyModelViewSet):
    """
    短视频平台数字人形象克隆 作者：xiaotao 版本号: 文档地址:
    """
    queryset = DigitalHumanLiveVideo.objects.filter(is_delete=0)
    serializer_class = ShortVideoDigitalHumanCloneSerializer
    lookup_field = "live_code"
    model_filter = ModelSaveData()
    pagination_class = CstPageNumberPagination
    filter_backends = [DigitalHumanCloneFilter]


class DigitalHumanProjectView(ModelViewSet):
    """
    口播视频 作者：xiaotao 版本号: 文档地址:
    """
    queryset = DigitalHumanProject.objects.filter(is_delete=0)
    serializer_class = DigitalHumanProjectSerializer
    lookup_field = "project_code"
    model_filter = ModelSaveData()
    pagination_class = CstPageNumberPagination
    filter_backends = [DigitalHumanCloneFilter]

    def retrieve(self, request, *args, **kwargs):
        user_code = request.user.user_code
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        project_code = self.kwargs[lookup_url_kwarg]
        with connections["default"].cursor() as cursor:
            cursor.execute(digital_human_sqls.HumanProjectDtl, [user_code, project_code])
            rows = dict_fetchall(cursor)
        if not rows:
            return CstResponse(RET.NO_DATE_ERROR, "未找到")
        exclude = ["create_by", "is_delete", "create_time", "voice_name"]
        main_dict = rows[0]
        dit_query = DigitalHumanLiveVideoDtl.objects.filter(project_code=project_code, is_delete=0).all()
        main_dict["live_sound_list"] = [model_to_dict(i, exclude=exclude) for i in dit_query]
        return CstResponse(RET.OK, data=main_dict)

    def create(self, request, *args, **kwargs):
        user_code = request.user.user_code
        data = request.data
        live_sound_list = data.get("live_sound_list") or []
        live_code = data.get("live_code")
        project_name = data.get("project_name") or ""
        sound_type = str(data.get("sound_type"))
        if not all([live_code, live_sound_list]):
            return CstResponse(RET.DATE_ERROR)

        v_obj = DigitalHumanLiveVideo.objects.filter(live_code=live_code).first()
        if not v_obj:
            return CstResponse(RET.DATE_ERROR, "你的形象视频未找到")
        if v_obj.make_status != 0:
            return CstResponse(RET.DATE_ERROR, "草稿状态不能生成口播视频")
        if v_obj.live_type == 1 and v_obj.create_by != user_code:
            return CstResponse(RET.DATE_ERROR, "数字人形象错误")
        if sound_type == "1":
            voice_code = data.get("voice_code")
            if not voice_code:
                return CstResponse(RET.DATE_ERROR, "请选择声音模型")
            voice_obj = VtTextToSpeechVoice.objects.filter(voice_code=voice_code, voice_type=2, create_by=user_code).first()
            if not voice_obj:
                return CstResponse(RET.DATE_ERROR, "声音错误")
            if voice_obj.v_status != 1:
                return CstResponse(RET.DATE_ERROR, "声音已过期,请联系客服续费")

        exclude = ["id", "make_status", "time_length"]
        live_save_data = self.model_filter.get_request_save_data(live_sound_list, DigitalHumanLiveVideoDtl, exclude=exclude)

        with transaction.atomic():
            exclude = ["id", "project_status"]
            save_data = self.model_filter.get_request_save_data(data, DigitalHumanProject, exclude=exclude)
            project_code = set_flow()
            save_data["project_code"] = project_code
            save_data["live_code"] = live_code
            save_data["create_by"] = user_code
            obj = DigitalHumanProject.objects.create(**save_data)
            insert_list = []
            for i, live_data in enumerate(live_save_data):
                live_script = live_data.get("live_script")
                if sound_type not in ["0", "1"]:
                    raise CstException(RET.DATE_ERROR, "类型错误")
                if sound_type == "1":
                    if not live_script:
                        raise CstException(RET.DATE_ERROR, "请先输入文字")
                live_data["project_code"] = obj.project_code
                live_data["live_dtl_code"] = set_flow()
                live_data["create_by"] = user_code
                live_data["video_name"] = project_name + "-" + str(i)
                insert_list.append(DigitalHumanLiveVideoDtl(**live_data))
            DigitalHumanLiveVideoDtl.objects.bulk_create(insert_list)

        return CstResponse(RET.OK, data=project_code)

    def update(self, request, *args, **kwargs):
        user_code = request.user.user_code
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        project_code = self.kwargs[lookup_url_kwarg]
        data = request.data
        live_code = data.get("live_code")
        project_name = data.get("project_name") or ""
        sound_type = str(data.get("sound_type"))

        p_obj = DigitalHumanProject.objects.filter(project_code=project_code, is_delete=0).first()
        if p_obj.project_status != 1:
            return CstResponse(RET.DATE_ERROR, "草稿状态才可以修改")
        # if live_code and p_obj.live_code != live_code and p_obj.project_status != 1:
        #     return CstResponse(RET.DATE_ERROR, "草稿状态才可以修改数字字人模型")

        v_obj = DigitalHumanLiveVideo.objects.filter(live_code=live_code).first()
        if v_obj.live_type == 1 and v_obj.create_by != user_code:
            return CstResponse(RET.DATE_ERROR, "数字人形象错误")
        if sound_type == "1":
            voice_code = data.get("voice_code")
            voice_obj = VtTextToSpeechVoice.objects.filter(voice_code=voice_code, voice_type=2, create_by=user_code).first()
            if not voice_obj:
                return CstResponse(RET.DATE_ERROR, "声音错误")
            if voice_obj.v_status != 1:
                return CstResponse(RET.DATE_ERROR, "声音已过期,请联系客服续费")

        live_sound_list = data.get("live_sound_list")
        exclude = ["project_code", "project_status"]
        dtl_exclude = ["live_code", "make_status", "time_length"]
        save_data = self.model_filter.get_request_save_data(data, DigitalHumanProject, exclude=exclude)
        live_save_list = self.model_filter.get_request_save_data(live_sound_list, DigitalHumanLiveVideoDtl, exclude=dtl_exclude)

        ids = [i["id"] for i in DigitalHumanLiveVideoDtl.objects.filter(project_code=project_code, is_delete=0).values("id")]
        with transaction.atomic():
            DigitalHumanProject.objects.filter(project_code=project_code, is_delete=0).update(**save_data)
            insert_list = []
            for i, live in enumerate(live_save_list):
                live["video_name"] = project_name + "-" + str(i)
                live["project_code"] = project_code
                try:
                    live_id = live.pop("id")
                except KeyError as e:
                    live_id = 0
                if live_id:  # 修改
                    ids.remove(live_id)
                    DigitalHumanLiveVideoDtl.objects.filter(id=live_id).update(**live)
                else:
                    sound_type = str(live.get("sound_type"))
                    live_script = live.get("live_script")
                    if sound_type == "1":
                        if not live_script:
                            raise CstException(RET.DATE_ERROR, "请先选择模型或输入文字")
                    live["live_dtl_code"] = set_flow()
                    live["create_by"] = user_code
                    insert_list.append(DigitalHumanLiveVideoDtl(**live))
            DigitalHumanLiveVideoDtl.objects.bulk_create(insert_list)  # 新增
            DigitalHumanLiveVideoDtl.objects.filter(id__in=ids).delete()  # 删除
        return CstResponse(RET.OK)

    def destroy(self, request, *args, **kwargs):
        user_code = request.user.user_code
        project_code_list = request.data.get("project_code_list") or []
        if not project_code_list or not isinstance(project_code_list, list):
            return CstResponse(RET.DATE_ERROR)
        with transaction.atomic():
            DigitalHumanProject.objects.filter(project_code__in=project_code_list, create_by=user_code,
                                               project_status=1).delete()
            DigitalHumanLiveVideoDtl.objects.filter(project_code__in=project_code_list, create_by=user_code,
                                                    make_status=1).delete()

        return CstResponse(RET.OK)

    def get_duration(self, request, *args, **kwargs):
        """
        获取声音时长
        """
        user_code = request.user.user_code
        data = request.data
        project_code = data.get("project_code")
        engine_code = data.get("engine_code")
        if not all([project_code, engine_code]):
            return CstResponse(RET.DATE_ERROR)
        v_obj = DigitalHumanProject.objects.filter(project_code=project_code, create_by=user_code).first()
        if not v_obj:
            return CstResponse(RET.DATE_ERROR, "项目未找到")

        oss_obj = ToOss()
        dtl_query = DigitalHumanLiveVideoDtl.objects.filter(project_code=project_code).all()
        time_length = 0
        if v_obj.sound_type == 1:
            voice_obj = VtTextToSpeechVoice.objects.filter(engine_code=engine_code, voice_code=v_obj.voice_code).first()
            engine = VtTextToSpeechEngine.objects.filter(engine_code=engine_code).first()
            if not voice_obj:
                return CstResponse(RET.DATE_ERROR, "声音错误")
            if voice_obj.v_status != 1:
                return CstResponse(RET.DATE_ERROR, "声音已过期,请联系客服续费")
            for i in dtl_query:
                if not i.live_sound_url:
                    tts_obj = VolcengineTTS(create_by=user_code, voice_obj=voice_obj, engine=engine)
                    send_data = {
                        "create_by": user_code,
                        "content": i.live_script
                    }
                    request_data = tts_obj.get_data(send_data)

                    oss_url = tts_obj.send_data(request_data, is_sv=1)["speech_url"]
                    if not oss_url:
                        return CstResponse(RET.DATE_ERROR, "声音合成失败，请重试")
                    i.live_sound_url = oss_url
                sound_url = i.live_sound_url
                duration = self.get_sound_time(sound_url, oss_obj)
                time_length += duration
                i.time_length = duration
                i.save()
        else:
            for i in dtl_query:
                sound_url = i.live_sound_url
                duration = self.get_sound_time(sound_url, oss_obj)
                time_length += duration
                i.time_length = duration
                i.save()
        return CstResponse(RET.OK, data={"time_length": int(time_length)})

    @LockRequest()
    @action(methods=["post"], detail=False)
    def short_video_get_duration(self, request, *args, **kwargs):
        """
        短视频平台获取声音时长,火山
        """
        user_code = request.user.user_code
        data = request.data
        project_code = data.get("project_code")
        engine_code = data.get("engine_code")
        if not all([engine_code, project_code]):
            return CstResponse(RET.DATE_ERROR)

        a_obj = DigitalHumanActivateNumber.objects.filter(create_by=user_code, activate_status=1, activate_type_id=3).first()
        if not a_obj:
            raise CstException(RET.NO_NUMBER, "无可用时长， 请先兑换卡密")

        v_obj = DigitalHumanProject.objects.filter(project_code=project_code, create_by=user_code).first()
        if not v_obj:
            return CstResponse(RET.DATE_ERROR, "项目未找到")

        oss_obj = ToOss()
        dtl_query = DigitalHumanLiveVideoDtl.objects.filter(project_code=project_code).all()
        time_length = 0

        with transaction.atomic():
            if v_obj.sound_type == 1:
                voice_obj = VtTextToSpeechVoice.objects.filter(engine_code=engine_code, voice_code=v_obj.voice_code).first()
                if not voice_obj:
                    return CstResponse(RET.DATE_ERROR, "声音错误")
                if voice_obj.v_status != 1:
                    return CstResponse(RET.DATE_ERROR, "声音已过期,请联系客服续费")
                for i in dtl_query:
                    if not i.live_sound_url:
                        tts_obj = VolcengineTTS(create_by=user_code, voice_obj=voice_obj, action_type=2)
                        send_data = {
                            "create_by": user_code,
                            "content": i.live_script
                        }
                        request_data = tts_obj.get_data(send_data)

                        oss_url = tts_obj.send_data(request_data)["speech_url"]
                        if not oss_url:
                            return CstResponse(RET.DATE_ERROR, "声音合成失败，请重试")
                        i.live_sound_url = oss_url
                    sound_url = i.live_sound_url
                    duration = self.get_sound_time(sound_url, oss_obj)
                    time_length += duration
                    i.time_length = duration
                    i.save()
            else:
                for i in dtl_query:
                    sound_url = i.live_sound_url
                    duration = self.get_sound_time(sound_url, oss_obj)
                    time_length += duration
                    i.time_length = duration
                    i.save()

            if a_obj.residue_number < time_length:
                raise CstException(RET.NO_NUMBER, "可用时长不足以完整输出所有视频， 请先兑换卡密")
            v_obj.project_status = 0
            v_obj.time_length = time_length
            v_obj.save()
        return CstResponse(RET.OK, data={"time_length": int(time_length)})

    @staticmethod
    def get_sound_time(sound_url, oss_obj):
        with oss_obj.batch_get_objects(sound_url) as video_obj:
            video = video_obj.read()
        if not video:
            return CstResponse(RET.DATE_ERROR, "音频读取失败，请重试")
        with BytesIO(video) as video_bytes:
            video_bytes.seek(0)  # 确保从头开始读取
            # with wave.openfp(video_bytes, 'rb') as audio_file:
            #     frames = audio_file.getnframes()
            #     rate = audio_file.getframerate()
            #
            # duration = frames / float(rate)
            audio = AudioSegment.from_file(video_bytes)

        # 获取音频时长，单位为毫秒
        duration_ms = len(audio)

        # 转换为秒
        duration = duration_ms / 1000
        return int(math.ceil(duration))


class NoAuthDigitalHumanProject(ModelViewSet):
    """
    算法机接口
    """
    authentication_classes = []
    lookup_field = "live_dtl_code"
    model_filter = ModelSaveData()

    @LockRequest()
    def get_list_make(self, request, *args, **kwargs):
        with connections["default"].cursor() as cursor:
            cursor.execute(digital_human_sqls.GetListMakeSql)
            rows = dict_fetchall(cursor)

        if rows:
            row = rows[0]
            DigitalHumanLiveVideoDtl.objects.filter(live_dtl_code=row["live_dtl_code"]).update(make_status=2)
            return CstResponse(RET.OK, data=row)
        else:
            return CstResponse(RET.OK)

    def update(self, request, *args, **kwargs):
        data = request.data
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        live_dtl_code = self.kwargs[lookup_url_kwarg]
        exclude = ["live_dtl_code", "live_code", "live_sound_url"]

        live_save_data = self.model_filter.get_request_save_data(data, DigitalHumanLiveVideoDtl, exclude=exclude)
        # DigitalHumanLiveVideoDtl.objects.filter(live_dtl_code=live_dtl_code, is_delete=0).update(**live_save_data)
        obj = DigitalHumanLiveVideoDtl.objects.filter(live_dtl_code=live_dtl_code, is_delete=0).first()
        for key, value in live_save_data.items():
            setattr(obj, key, value)
        obj.save()
        a_obj = DigitalHumanActivateNumber.objects.filter(create_by=obj.create_by, activate_status=1, activate_type_id=3).first()
        if a_obj:
            a_obj.residue_number -= int(obj.time_length)
            if a_obj.residue_number <= 0:
                a_obj.activate_status = 4
            a_obj.save()
            DigitalHumanActivateConsumeHistory.objects.create(
                create_by=request.user.user_code,
                activate_type_id=3,
                usage_number=int(obj.time_length)
            )
        return CstResponse(RET.OK)


class NoAuthSoundCloneView(ViewSet):
    """阿里克隆"""
    authentication_classes = []

    def create(self, request):
        list_customized_voice_task()
        return CstResponse(RET.OK)

    def update(self, request):
        data = request.data
        voice_code = data.get("voice_code")
        if not all([voice_code]):
            return CstResponse(RET.DATE_ERROR)
        obj = DigitalHumanCustomizedVoice.objects.filter(voice_code=voice_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "该声音模型未找到")
        if obj.voice_status != 1:
            return CstResponse(RET.DATE_ERROR, "请先完成支付在提交")
        sdk_obj = SoundCloneSdk()
        resp = sdk_obj.submit_voice(obj.voice_name, obj.gender)
        redis_conn = get_redis_connection('cache')
        obj.voice_status = 2  # 修改状态为克隆中
        obj.save()
        redis_conn.delete(obj.voice_name)
        return CstResponse(RET.OK, data=resp)


class SoundCloneView(ViewSet):
    """
    声音克隆
    """

    @cache_response(timeout=cache_time, cache='cache')
    def get_for_voice(self, request, *args, **kwargs):
        """
        获取朗读文字
        """
        obj = SoundCloneSdk()
        resp = obj.get_for_customized_voice()
        return CstResponse(RET.OK, data=resp)

    def voice_audio_detect(self, request, *args, **kwargs):
        """
        音频检测
        支持的输入格式：单声道（mono）16bit采样位数音频，包括无压缩的PCM、WAV格式。
        音频采样率：16000 Hz、24000 Hz、48000 Hz。
        """
        data = request.data
        user_code = request.user.user_code
        voice_name = data.get("voice_name")
        voice_list = data.get("voice_list")
        if not all([voice_name, voice_list]):
            return CstResponse(RET.DATE_ERROR)
        if not DigitalHumanCustomizedVoice.objects.filter(voice_name=voice_name, create_by=user_code).exists():
            return CstResponse(RET.DATE_ERROR, "该名称数据未找到")
        redis_conn = get_redis_connection('cache')

        obj = SoundCloneSdk()       # 状态未提交训练前可以修改
        obj.customized_voice_audio_detect(voice_name, voice_list, redis_conn)
        return CstResponse(RET.OK)

    def submit_customized_voice(self, request, *args, **kwargs):
        """
        提交训练
        """
        user_code = request.user.user_code
        data = request.data
        voice_name = data.get("voice_name")
        gender = data.get("gender")
        if gender not in ["female", "male"]:
            return CstResponse(RET.DATE_ERROR, "性别选择错误")
        obj = DigitalHumanCustomizedVoice.objects.filter(voice_name=voice_name, create_by=user_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "该名称数据未找到")
        if obj.voice_status == 0:
            return CstResponse(RET.DATE_ERROR, "请先完成支付在提交")
        sdk_obj = SoundCloneSdk()
        resp = sdk_obj.submit_voice(voice_name, gender)
        redis_conn = get_redis_connection('cache')
        obj.voice_status = 2    # 修改状态为克隆中
        obj.save()
        redis_conn.delete(obj.voice_name)
        return CstResponse(RET.OK, data=resp)

    def list_customized_voice(self, request, *args, **kwargs):
        """获取训练结果"""
        user_code = request.user.user_code
        data = request.query_params
        voice_name = data.get("voice_name")
        obj = DigitalHumanCustomizedVoice.objects.filter(voice_name=voice_name, create_by=user_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "该名称数据未找到")
        resp = {
            "reason": obj.reason,
            "voice_status": obj.voice_status,
        }
        # data = request.query_params
        # voice_name = data.get("voice_name")
        # if not voice_name:
        #     return CstResponse(RET.DATE_ERROR)
        # obj = SoundCloneSdk()
        # resp = obj.list_customized_voice(voice_name)
        return CstResponse(RET.OK, data=resp)


class CustomizedVoiceView(NewSqlMixin, TyModelViewSet):
    """
    声音克隆逻辑视图
    """
    query_sql = digital_human_sqls.CustomizedVoiceSql
    sort_field = ["create_time"]
    where = " and "
    main_table = "a"
    queryset = DigitalHumanCustomizedVoice.objects.filter(is_delete=0)
    serializer_class = CustomizedVoiceSerializer

    def set_query_sql(self):
        user_code = self.request.user.user_code
        voice_status = self.request.query_params.get("voice_status")
        voice_name = self.request.query_params.get("voice_name")
        self.query_sql += f" and create_by = '{user_code}'"
        if voice_status:
            self.query_sql += f" and a.voice_status = {voice_status}"
        if voice_name:
            self.query_sql += f" and a.voice_name = '{voice_name}'"
        return self.query_sql

    def list(self, request, *args, **kwarg):
        """
        :param request:
        :param args:
        :param kwarg:
        :return:
        """
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        redis_conn = get_redis_connection('cache')
        voice_info = redis_conn.get(instance.voice_name)
        if voice_info:
            voice_info = json.loads(voice_info)
        data["voice_info"] = voice_info or []
        return CstResponse(RET.OK, data=data)


class VoiceGenerateHistoryView(NewSqlMixin, TyModelViewSet):
    query_sql = digital_human_sqls.VoiceGenerateHistorySql
    sort_field = ["create_time"]
    where = " and "
    main_table = "a"
    model_filter = ModelSaveData()

    def set_query_sql(self):
        user_code = self.request.user.user_code
        voice_code = self.request.query_params.get("voice_code")
        self.query_sql += f" and create_by = '{user_code}'"
        if voice_code:
            self.query_sql += f" and voice_code = '{voice_code}'"
        return self.query_sql

    def list(self, request, *args, **kwarg):
        """
        :param request:
        :param args:
        :param kwarg:
        :return:
        """
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    def create(self, request, *args, **kwargs):
        """生成音频"""
        data = request.data
        user_code = request.user.user_code
        live_script = data.get("live_script")
        model_id = data.get("model_id")
        voice_code = data.get("voice_code")
        volume = data.get("volume") or 50
        speech_rate = data.get("speech_rate") or 0
        pitch_rate = data.get("pitch_rate") or 0
        token = data.get("token")
        if not all([live_script, model_id, token, voice_code]):
            return CstResponse(RET.DATE_ERROR)
        obj = DigitalHumanCustomizedVoice.objects.filter(voice_code=voice_code, create_by=user_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "未找到可用的声音模型")
        if obj.voice_status != 3:
            return CstResponse(RET.DATE_ERROR, "声音模型未完成")

        obj = VoiceTts(token)
        oss_url = obj.start(live_script, model_id, volume, speech_rate, pitch_rate)
        if not oss_url:
            return CstResponse(RET.DATE_ERROR, "合成失败，请重试")
        exclude = ["id"]
        save_data = self.model_filter.get_request_save_data(data, DigitalHumanVoiceGenerateHistory, exclude=exclude)
        save_data["h_code"] = set_flow()
        save_data["live_sound_url"] = oss_url
        save_data["create_by"] = user_code
        DigitalHumanVoiceGenerateHistory.objects.create(**save_data)
        return CstResponse(RET.OK, data=oss_url)


class NoAuthVoiceGenerateHistoryView(ModelViewSet):
    """算法机调用"""
    model_filter = ModelSaveData()
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        """生成音频"""
        data = request.data
        user_code = data.get("user_code")
        live_dtl_code = data.get("live_dtl_code")
        voice_code = data.get("voice_code")
        token = data.get("token")
        if not all([user_code, token, voice_code, live_dtl_code]):
            return CstResponse(RET.DATE_ERROR)
        obj = DigitalHumanCustomizedVoice.objects.filter(voice_code=voice_code, create_by=user_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "未找到可用的声音模型")
        if obj.voice_status != 3:
            return CstResponse(RET.DATE_ERROR, "声音模型未完成")

        v_obj = DigitalHumanLiveVideoDtl.objects.filter(live_dtl_code=live_dtl_code).first()
        if not v_obj:
            return CstResponse(RET.DATE_ERROR, "未找到")
        live_script = v_obj.live_script

        tts_obj = VoiceTts(token)
        oss_url = tts_obj.start(live_script, obj.model_id, v_obj.volume, v_obj.speech_rate, v_obj.pitch_rate)
        if not oss_url:
            return CstResponse(RET.DATE_ERROR, "合成失败，请重试")
        exclude = ["id"]
        save_data = self.model_filter.get_request_save_data(data, DigitalHumanVoiceGenerateHistory, exclude=exclude)
        save_data["h_code"] = set_flow()
        save_data["live_sound_url"] = oss_url
        save_data["live_script"] = live_script
        save_data["create_by"] = user_code
        with transaction.atomic():
            DigitalHumanVoiceGenerateHistory.objects.create(**save_data)
            v_obj.live_sound_url = oss_url
            v_obj.save()
        return CstResponse(RET.OK, data=oss_url)


class GgetVideoCover(ViewSet):
    """
    获取视频封面
    """
    def create(self, request, *args, **kwargs):
        live_video_url = request.data.get("live_video_url")
        if not live_video_url:
            return CstResponse(RET.DATE_ERROR)

        oss_obj = ToOss()
        with oss_obj.batch_get_objects(live_video_url) as video_obj:
            video = video_obj.read()
        if not video:
            return CstResponse(RET.DATE_ERROR, "视频读取失败，请重试")
        file_name = ""
        with BytesIO(video) as video_bytes:
            dir_s = os.path.join(BASE_DIR, 'static')
            # with tempfile.TemporaryFile(dir=dir_s) as f:
            with tempfile.NamedTemporaryFile(dir=dir_s, delete=False) as f:
                # 将BytesIO对象中的内容写入临时文件
                f.write(video_bytes.read())
                # 使用OpenCV从临时文件中读取视频
                file_name = f.name
                video_capture = cv2.VideoCapture(file_name)

        # 检查视频是否已经打开
        if not video_capture.isOpened():
            return CstResponse(RET.DATE_ERROR, "视频打开失败，请重试")

        # 读取视频的第一帧
        ret, frame = video_capture.read()

        if not ret:
            return CstResponse(RET.DATE_ERROR, "封面读取失败，请重试")

        # 关闭视频
        video_capture.release()
        os.remove(file_name)
        is_success, buffer = cv2.imencode(".jpg", frame)
        if not is_success:
            return CstResponse(RET.DATE_ERROR, "封面生成失败，请重试")

        with BytesIO(buffer) as image_bytes_io:
            b_im = image_bytes_io.getvalue()
        # file_con = remove(b_im)
        oss_url = oss_obj.main("digital_human", oss_dir="static", file_con=b_im)

        return CstResponse(RET.OK, data=oss_url)


class AudioConversion(ViewSet):
    """音频转换
    音频检测
    支持的输入格式：单声道（mono）16bit采样位数音频，包括无压缩的PCM、WAV格式。
    音频采样率：16000 Hz、24000 Hz、48000 Hz。"""

    def create(self, request):
        image = request.FILES.get("image")  # 图像
        file_extension = request.data.get("file_extension") or "wav"  #
        if not image:
            return CstResponse(RET.DATE_ERROR)
        limit_mb = 50
        if image.size > limit_mb * 1024 * 1024:
            return CstResponse(RET.DATE_ERROR, "文件过大，请换个文件重试")
        with BytesIO(image.read()) as video_bytes:
            video_bytes.seek(0)  # 确保从头开始读取
            audio = AudioSegment.from_file(video_bytes)
        # 设置采样率为16000 Hz
        audio = audio.set_frame_rate(48000)
        # 将声音转换为单声道
        audio = audio.set_channels(1)
        # 将采样位数设置为16bit
        audio = audio.set_sample_width(2)
        # 创建BytesIO对象
        with BytesIO() as output:
            # 导出为wav格式音频到BytesIO对象
            audio.export(output, format="wav")
            # 读取BytesIO对象中的数据
            output.seek(0)
            output_data = output.read()

        oss_dir = request.data.get("oss_dir") or "static"  #
        cate = request.data.get("cate") or "digital_human"  #
        init = ToOss()
        new_url = init.main(cate, oss_dir=oss_dir, file_con=output_data, file_extension=file_extension)
        return CstResponse(RET.OK, data={"oss_url": new_url})
