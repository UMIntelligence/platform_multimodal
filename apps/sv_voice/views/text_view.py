#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import json

from django.db import connections
from django_redis import get_redis_connection
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from language.language_pack import RET
from server_chat import settings
from sv_voice.models.speech_models import SpeechRecognitionHistory
from sv_voice.serializers.audio_serializers import SpeechRecognitionSerializer
from sv_voice.sqls import speech_sqls
from sv_voice.tasks import set_ali_access_token
from utils.ali_sdk import RecordingFileRecognition
from utils.cst_class import CstResponse
from utils.sql_utils import TySqlMixin, dict_fetchall, NewSqlMixin


class Test(APIView):
    """

    """
    def get(self, request):
        # set_ali_access_token()
        # redis_conn = get_redis_connection('chat')
        # data = [
        #     {
        #         "512*512": "static/picture/87d934dd-cfa6-46c8-a145-49bfcafda023.png",
        #         "512*768": "static/picture/db7571aa-8cf0-4961-811a-d484aa4a9386.png",
        #         "768*512": "static/picture/5f4c6faa-6f97-4649-9cf8-849a27aa1a04.png",
        #     },
        #     {
        #         "512*512": "static/picture/ebb8a53a-2187-4988-9965-014403efe4f2.png",
        #         "512*768": "static/picture/3a1cf1bf-d7fd-4648-83fe-a7eb68effaeb.png",
        #         "768*512": "static/picture/51f44b09-8721-4dcd-82b5-6d509f5b4d2f.png",
        #     },
        # ]
        # sd_ultrasound = json.dumps(data)
        # redis_conn.set("sd_ultrasound", sd_ultrasound)
        return CstResponse(RET.OK)


class AliToken(APIView):
    authentication_classes = []

    def get(self, request):
        redis_conn = get_redis_connection('default')
        token = redis_conn.get("ali_audio")
        token = token.decode("utf-8")
        return CstResponse(RET.OK, data={"token": token})


class SpeechRecognition(NewSqlMixin, ModelViewSet):
    """
    语音识别文本保存列表视图 作者：xiaotao 版本号: 文档地址:
    """
    queryset = SpeechRecognitionHistory.objects.filter(is_delete=0)
    serializer_class = SpeechRecognitionSerializer
    sort_field = ["create_time"]
    sort_type = "desc"
    main_table = "a"
    where = " and "
    query_sql = speech_sqls.SpeechHistorySql
    lookup_field = "speech_code"

    def set_query_sql(self):
        query_sql = self.query_sql
        r_type = self.request.query_params.get('r_type')
        create_by = self.request.user.user_code
        if create_by:
            query_sql += f" and create_by= '{create_by}'"
        if r_type:
            query_sql += f" and r_type={r_type}"

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

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            # If 'prefetch_related' has been applied to a queryset, we need to
            # forcibly invalidate the prefetch cache on the instance.
            instance._prefetched_objects_cache = {}

        return CstResponse(RET.OK, data=serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return CstResponse(RET.OK)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return CstResponse(RET.OK, data=serializer.data)


class FileIdentifier(APIView):
    """
    文件识别
    """
    def get(self, request):
        task_id = request.query_params.get("task_id")
        if not task_id:
            return CstResponse(RET.DATE_ERROR)
        obj = RecordingFileRecognition()
        resp = obj.get_send_request(task_id)
        return CstResponse(RET.OK, data=resp)

    def post(self, request):
        file_link = request.data.get("file_link")
        if not file_link:
            return CstResponse(RET.DATE_ERROR)
        file_link = settings.NETWORK_STATION + file_link
        obj = RecordingFileRecognition()
        task_id = obj.send_request(file_link)
        return CstResponse(RET.OK, data={"task_id": task_id})


class FileIdentifierCall(APIView):
    """
    文件识别回调
    """
    authentication_classes = []

    def post(self, request):
        a = {'Result': {'Sentences':
                            [{'EndTime': 2610, 'SilenceDuration': 1, 'SpeakerId': '1', 'BeginTime': 1110, 'Text': '北京的天气。', 'ChannelId': 0, 'SpeechRate': 200, 'EmotionValue': 6.0}]},
             'BizDuration': 3264, 'RecDuration': 3264, 'RequestTime': 1691653768108, 'SolveTime': 1691653771691,
             'TaskId': '1f0a94670abb49fa9424b6669a37596a', 'StatusCode': 21050000, 'StatusText': 'SUCCESS'}

        data = request.data
        print(data)

        return CstResponse(RET.OK)
