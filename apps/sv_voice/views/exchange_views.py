#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
"""
卡密兑换

"""
import datetime

from dateutil.relativedelta import relativedelta
from django.db import connections, transaction
from django.db.models import Sum
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from language.language_pack import RET
from sv_voice.models.exchange_models import DigitalHumanActivateCode, DigitalHumanActivateNumber, \
    DigitalHumanActivateExchangeHistory, AdBusiness
from sv_voice.models.voice_train_models import VtVoiceId
from utils.cst_class import CstResponse, CstException
from utils.redis_lock import LockRequest
from utils.sql_utils import NewSqlMixin, dict_fetchall


class ActivateExchangeTasks(APIView):
    """卡密过期定时任务"""
    authentication_classes = []

    def post(self, request):
        now_date = timezone.now()
        DigitalHumanActivateCode.objects.using("admin_video").filter(expired_date__lt=now_date, activation_status=1).update(
            activation_status=3
        )
        query_set = DigitalHumanActivateNumber.objects.filter(expired_date__lt=now_date, activate_status=1).all()
        for obj in query_set:
            obj.activate_status = 3
            if obj.activate_type_id == 2:
                v_obj = VtVoiceId.objects.filter(user_code=obj.create_by, voice_status=2).first()
                try:
                    v_obj.voice_status = 1
                    v_obj.user_code = ""
                    v_obj.save()
                except Exception as e:
                    pass
            obj.save()
        return CstResponse(RET.OK)


class ActivateExchange(NewSqlMixin, ViewSet):
    sort_field = ["create_time"]
    sort_type = "desc"
    where = " and "
    query_sql = """SELECT activate_code, activate_type_id,
    DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time,
    DATE_FORMAT(expired_date, '%Y-%m-%d %H:%i:%s') expired_date
        FROM digital_human_activate_exchange_history
        WHERE 0=0 """

    def set_query_sql(self):
        create_by = self.request.user.user_code
        activate_type_id = self.request.query_params.get("activate_type_id")
        self.query_sql += f" and create_by= '{create_by}'"
        if activate_type_id:
            self.query_sql += f" and activate_type_id= {activate_type_id}"

        return self.query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})

    @LockRequest()
    def create(self, request, *args, **kwargs):
        """
        兑换
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        user = request.user
        activate_code = request.data.get("activate_code")
        obj = DigitalHumanActivateCode.objects.using("admin_video").filter(activate_code=activate_code).first()
        if not obj:
            return CstResponse(RET.DATE_ERROR, "卡密未找到")

        if obj.activation_status != 1:
            status_dict = {
                2: "卡密已被使用",
                3: "卡密已过期"
            }
            return CstResponse(RET.DATE_ERROR, status_dict.get(obj.activation_status))

        if obj.is_freeze:
            return CstResponse(RET.DATE_ERROR, "卡密已被冻结")

        # 校验用户和邀请用户
        if obj.create_by != user.invitation_code:
            return CstResponse(RET.DATE_ERROR, "请使用邀请人的卡密")

        residue_number_dict = {
            3: 432000   # 120小时，秒
        }
        expired_date = datetime.datetime.now() - relativedelta(years=-1)
        if obj.activate_type_id == 4:
            a_obj = DigitalHumanActivateNumber.objects.filter(create_by=user.user_code, activate_type_id=obj.activate_type_id, activate_status=1).order_by("-id").first()
            if a_obj:
                expired_date = a_obj.expired_date - relativedelta(years=-1)

        with transaction.atomic():
            # if obj.activate_type_id == 3:
            #     a_obj = DigitalHumanActivateNumber.objects.filter(create_by=user.user_code,
            #                                                       activate_type_id=obj.activate_type_id,
            #                                                       activate_status=4, residue_number__lt=0).first()
            #     if a_obj:
            #         residue_number = residue_number_dict.get(obj.activate_type_id) + a_obj.residue_number  # 前面多用的补上去
            #         a_obj.residue_number = 0
            #         a_obj.save()

            DigitalHumanActivateNumber.objects.create(
                activate_code=obj.activate_code,
                activate_type_id=obj.activate_type_id,
                expired_date=expired_date,
                residue_number=residue_number_dict.get(obj.activate_type_id) or 0,
                create_by=user.user_code
            )
            DigitalHumanActivateExchangeHistory.objects.create(     # 操作历史
                activate_code=obj.activate_code,
                activate_type_id=obj.activate_type_id,
                expired_date=expired_date,
                create_by=user.user_code
            )
            if obj.activate_type_id == 2:
                model_obj = VtVoiceId.objects.filter(voice_status=1).first()
                if not model_obj:
                    raise CstException(RET.DATE_ERROR, "声音id已用尽，请联系客服添加")

                model_obj.voice_status = 2
                model_obj.user_code = user.user_code
                model_obj.save()
        obj.consumed_by = user.user_code
        obj.start_date = datetime.datetime.now()
        obj.activation_status = 2
        obj.save()
        return CstResponse(RET.OK)

    @action(methods=["get"], detail=False)
    def get_activate_residue_number(self, request, *args, **kwargs):
        user_code = request.user.user_code

        activate_number = {}
        number = DigitalHumanActivateNumber.objects.filter(activate_status=1, create_by=user_code, activate_type_id=1).count()
        activate_number[1] = number
        number = DigitalHumanActivateNumber.objects.filter(activate_status=1, create_by=user_code, activate_type_id=2).count()
        activate_number[2] = number
        number = DigitalHumanActivateNumber.objects.filter(activate_status=1, create_by=user_code, activate_type_id=3).aggregate(
            sum_residue_number=Sum('residue_number'))["sum_residue_number"] or 0
        activate_number[3] = number
        return CstResponse(RET.OK, data=activate_number)


class ActivateConsume(NewSqlMixin, ViewSet):
    sort_field = ["create_time"]
    sort_type = "desc"
    where = " and "
    query_sql = """SELECT usage_number, activate_type_id,
    DATE_FORMAT(create_time, '%Y-%m-%d %H:%i:%s') create_time
        FROM digital_human_activate_consume_history
        WHERE 0=0 """

    def set_query_sql(self):
        create_by = self.request.user.user_code
        activate_type_id = self.request.query_params.get("activate_type_id")
        self.query_sql += f" and create_by= '{create_by}'"
        if activate_type_id:
            self.query_sql += f" and activate_type_id= {activate_type_id}"

        return self.query_sql

    def list(self, request, *args, **kwargs):
        total = self.get_query_total()
        with connections["default"].cursor() as cursor:
            cursor.execute(self.query_sql_holder)
            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data={'total': total, 'data': rows})


class GetAdBusiness(APIView):

    def get(self, request):
        user = request.user
        invitation_code = user.invitation_code

        rows = AdBusiness.objects.using("admin_video").filter(create_by=invitation_code).values(
            "business_name", "business_logo", "mobile", "wx_url", "address", "business_desc"
        )
        row = {}
        if rows:
            row = rows[0]
        return CstResponse(RET.OK, data=row)

