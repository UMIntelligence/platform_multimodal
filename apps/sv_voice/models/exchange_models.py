#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models
from django.utils import timezone

from utils.base_models import BaseModel


class AdBusiness(models.Model):
    user_code = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="客户端用户编号")
    business_name = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="商家名称")
    business_logo = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="商家logo")
    business_desc = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="商家简介")
    mobile = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="手机号")
    wx_url = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="微信二维码")
    address = models.CharField(max_length=20, blank=True, null=True, default="", verbose_name="地址")
    create_by = models.CharField(max_length=64, blank=True, null=True, default="", help_text="创建人唯一编号")
    objects = models.Manager()

    class Meta:
        managed = False
        db_table = 'ad_business'
        verbose_name = '商家信息'
        verbose_name_plural = '商家信息'


class DigitalHumanActivateType(models.Model):
    type_name = models.CharField(max_length=64, default='', blank=True, verbose_name='激活码类型名称')
    desc = models.CharField(max_length=512, default='', blank=True, verbose_name='描述')

    class Meta:
        db_table = 'digital_human_activate_type'
        verbose_name = '数字人激活码类型表'
        verbose_name_plural = '数字人激活码表'
        # app_label = 'admin'


class DigitalHumanActivateCode(models.Model):
    consumed_by = models.CharField(max_length=20, default='', blank=True, verbose_name='消费者id')
    activate_code = models.CharField(max_length=64, unique=True, default='', blank=True, verbose_name='激活码')
    activation_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：未激活，2：已使用, 3已过期,")
    activate_type_id = models.IntegerField(blank=True, null=True, default=-1, help_text="类型id：1：形象克隆，2：声音克隆，3：视频时长，4：通用功能")
    is_freeze = models.IntegerField(blank=True, null=True, default=0, help_text="是否冻结：0：否,1是")
    expired_date = models.DateTimeField(blank=True, null=True, default=None, verbose_name="过期时间")
    start_date = models.DateTimeField(blank=True, null=True, default=None, verbose_name="激活时间")
    desc = models.CharField(max_length=512, default='', blank=True, verbose_name='描述')

    create_by = models.CharField(max_length=64, blank=True, null=True, default="", help_text="创建人唯一编号")
    create_time = models.DateTimeField(blank=True, null=True, default=timezone.now, verbose_name="创建时间")
    modify_by = models.CharField(max_length=64, blank=True, null=True, default="", help_text="最近修改人")
    modify_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")
    is_delete = models.IntegerField(blank=True, null=True, default=0, help_text="是否删除。1：删除，0：否")
    objects = models.Manager()

    class Meta:
        db_table = 'digital_human_activate_code'
        verbose_name = '数字人激活码表'
        verbose_name_plural = '数字人激活码表'
        # app_label = 'admin'


class DigitalHumanActivateNumber(BaseModel):
    activate_code = models.CharField(max_length=64, unique=True, default='', blank=True, verbose_name='激活码')
    activate_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：待使用，2：已使用，3：已过期,4已用尽")
    activate_type_id = models.IntegerField(blank=True, null=True, default=-1, help_text="类型id：1：形象克隆，2：声音克隆，3：视频时长，4：通用功能")
    expired_date = models.DateTimeField(blank=True, null=True, default=None, verbose_name="过期时间")
    residue_number = models.IntegerField(blank=True, null=True, default=0, help_text="剩余数/秒")

    class Meta:
        db_table = 'digital_human_activate_number'
        verbose_name = '数字人激活码表'
        verbose_name_plural = '数字人激活数量'


class DigitalHumanActivateExchangeHistory(BaseModel):
    activate_code = models.CharField(max_length=64, unique=True, default='', blank=True, verbose_name='激活码')
    activate_type_id = models.IntegerField(blank=True, null=True, default=1, help_text="类型id：1：形象克隆，2：声音克隆，3：视频时长，4：通用功能")
    expired_date = models.DateTimeField(blank=True, null=True, default=None, verbose_name="过期时间")

    class Meta:
        db_table = 'digital_human_activate_exchange_history'
        verbose_name = '数字人激活码历史表'
        verbose_name_plural = '数字人激活数量'


class DigitalHumanActivateConsumeHistory(BaseModel):
    activate_type_id = models.IntegerField(blank=True, null=True, default=1, help_text="类型id：1：形象克隆，2：声音克隆，3：视频时长，4：通用功能")
    usage_number = models.IntegerField(blank=True, null=True, default=0, help_text="使用数")

    class Meta:
        db_table = 'digital_human_activate_consume_history'
        verbose_name = '数字人激活码历史表'
        verbose_name_plural = '数字人激活数量'

