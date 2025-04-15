#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class UUUsersRealNameAuthentication(BaseModel):

    user_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="用户编号")
    address = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="地址")
    birthday = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="生日")
    name = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="姓名")
    id_card_number = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="身份证号")
    gender = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="性别")
    nation = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="民族")
    expire_time = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="身份证失效日期")
    issue_authority = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="身份证签发机关")
    issue_time = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="身份证生效日期")
    front_image_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="身份证图片的正面信息")
    back_image_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="身份证图片的反面信息")

    class Meta:
        managed = False
        db_table = 'uu_users_real_name_authentication'
        verbose_name = '用户实名认证信息表'
        verbose_name_plural = verbose_name


class VtVoiceTrainHistory(BaseModel):

    train_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="音色编号")
    voice_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="第三方唯一声音id")
    voice_name = models.CharField(max_length=15, blank=True, null=True, default="", verbose_name="音色名称")
    voice_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：创建未付款，2:训练中，3：制作成功，4制作失败, 5启用/生效中,6:过期")
    voice_type = models.IntegerField(blank=True, null=True, default=1, help_text="类型1:火山，2其他")
    remark = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="备注")
    demo_audio = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="demo url")
    audios = models.JSONField(verbose_name="参与声音训练列表", default=list)
    expire_time = models.DateTimeField(blank=True, null=True, default=None, verbose_name="过期时间")

    class Meta:
        managed = False
        db_table = 'vt_voice_train_history'
        verbose_name = '声音训练记录'
        verbose_name_plural = verbose_name


class VtVoiceId(BaseModel):
    """"""
    voice_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="第三方唯一声音id")
    voice_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：待分配，2:已分配，3：已使用")
    user_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="使用者")

    class Meta:
        managed = False
        db_table = 'vt_voice_id'
        verbose_name = '声音id表'
        verbose_name_plural = verbose_name
