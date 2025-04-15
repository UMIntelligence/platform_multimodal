#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class DigitalHumanExperience(BaseModel):

    user_name = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="姓名")
    mobile = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="手机")

    class Meta:
        managed = False
        db_table = 'vd_digital_human_experience'
        verbose_name = '数字体验记录表'
        verbose_name_plural = verbose_name


class DigitalHumanFile(BaseModel):

    file_code = models.CharField(max_length=65, blank=True, null=True, default="", verbose_name="唯一编号")
    file_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="文件地址")
    file_name = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="文件")
    f_type = models.IntegerField(blank=True, null=True, default=1, help_text="1:形象克隆，2：声音克隆")
    file_type = models.IntegerField(blank=True, null=True, default=1, help_text="文件类型1:图片，2：音频，3：视频")

    class Meta:
        managed = False
        db_table = 'vd_digital_human_file'
        verbose_name = '数字体验记录表'
        verbose_name_plural = verbose_name


class DigitalHumanLiveVideo(BaseModel):

    live_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    live_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="名称")
    live_video_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="视频url")
    video_cover_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="视频封面url")
    live_video_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="视频唯一号")
    power_attorney_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="授权书url")
    make_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：草稿，0:支付完成，")
    live_type = models.IntegerField(blank=True, null=True, default=1, help_text="数字人类型1：专属，0:公模，")

    class Meta:
        managed = False
        db_table = 'vd_digital_human_live_video'
        verbose_name = '数字人视频表'
        verbose_name_plural = verbose_name


class DigitalHumanProject(BaseModel):

    live_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    project_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="项目唯一编号")
    project_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="名称")
    project_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：草稿，0：支付成功")
    v_type = models.IntegerField(blank=True, null=True, default=0, help_text="类型0:数字人，1视频")
    sound_type = models.IntegerField(blank=True, null=True, default=0, help_text="声音类型0:录音，1阿里克隆")
    voice_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="声音模型唯一编号,类型为1必传")
    time_length = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=0.00, help_text="声音总时长秒")

    class Meta:
        managed = False
        db_table = 'vd_digital_human_project'
        verbose_name = '数字人项目视频表'
        verbose_name_plural = verbose_name


class DigitalHumanLiveVideoDtl(BaseModel):

    project_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="项目唯一编号")
    video_name = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="数字人名称")
    live_dtl_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    live_script = models.TextField(blank=True, null=True, default="", verbose_name="声音脚本")
    live_sound_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="声音url")
    sound_name = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="声音名称")
    complete_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="生成完成的url")
    remark = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="")
    make_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：草稿，2:制作中3：制作成功，4制作失败")
    time_length = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=0.00, help_text="声音时长")
    voice_name = models.CharField(max_length=128, blank=True, null=True, default="", verbose_name="声音名称")
    volume = models.IntegerField(blank=True, null=True, default=50, help_text="音量，范围是0~100。默认值：50。")
    speech_rate = models.IntegerField(blank=True, null=True, default=0, help_text="语速,取值范围：-500~500")
    pitch_rate = models.IntegerField(blank=True, null=True, default=0, help_text="语调,取值范围：-500~500")

    class Meta:
        managed = False
        db_table = 'vd_digital_human_live_video_dtl'
        verbose_name = '数字人视频子表'
        verbose_name_plural = verbose_name


class DigitalHumanCustomizedVoice(BaseModel):

    voice_name = models.CharField(max_length=15, blank=True, null=True, default="", verbose_name="声音名称")
    model_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="第三方唯一编号")
    voice_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    gender = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="声音性别")
    scenario = models.CharField(max_length=64, blank=True, null=True, default="story", verbose_name="场景，取值范围如下：story：故事interaction：交互navigation：导航")
    voice_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：创建完成，2:克隆中3：克隆成功，4克隆失败,0支付完成")
    voice_type = models.IntegerField(blank=True, null=True, default=1, help_text="类型1:阿里克隆，2其他,0:通用免费阿里'")
    reason = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="原因")

    class Meta:
        managed = False
        db_table = 'vd_digital_human_customized_voice'
        verbose_name = '数字人语音克隆表'
        verbose_name_plural = verbose_name


class DigitalHumanVoiceGenerateHistory(BaseModel):

    voice_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    h_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    live_sound_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="声音url")
    live_script = models.TextField(blank=True, null=True, default="", verbose_name="文本")
    h_status = models.IntegerField(blank=True, null=True, default=1, help_text="状态1：制作成功，2:制作失败")
    h_type = models.IntegerField(blank=True, null=True, default=1, help_text="类型1:阿里克隆，2录音文件")
    reason = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="原因")
    volume = models.IntegerField(blank=True, null=True, default=50, help_text="音量，范围是0~100。默认值：50。")
    speech_rate = models.IntegerField(blank=True, null=True, default=0, help_text="语速,取值范围：-500~500")
    pitch_rate = models.IntegerField(blank=True, null=True, default=0, help_text="语调,取值范围：-500~500")

    class Meta:
        managed = False
        db_table = 'vd_digital_human_voice_generate_history'
        verbose_name = '数字人语音生成记录表'
        verbose_name_plural = verbose_name

