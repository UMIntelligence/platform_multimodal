#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import models

from utils.base_models import BaseModel


class CCChatSession(BaseModel):
    CHAT_TYPE = (
        (0, "gpt3.5"),
        (1, "gpt4.0"),
        (2, "dell2绘图"),
        (3, "百度绘图"),
        (4, "文心一言"),
        (5, "科大讯飞"),
        (6, "mj绘画"),
        (7, "ClaudeChat"),
        (8, "ChatGLM"),
        (9, "sd"),
        (10, "QwEn"),
        (11, "SenseNova"),
    )

    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="会话唯一编号")
    title = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="标题")
    model = models.CharField(max_length=128, blank=True, null=True, default="", verbose_name="会话模型")
    question_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="人物id")
    chat_type = models.IntegerField(blank=True, null=True, default=0, choices=CHAT_TYPE, verbose_name="类型")
    remark = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="")
    image_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="")
    scenario_type = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="场景类型")

    class Meta:
        managed = False
        db_table = 'cc_chat_session'
        verbose_name = '会话表'
        verbose_name_plural = verbose_name


class CCChatSessionDtl(BaseModel):
    ACTION_TYPE = (
        (1, "正常对话"),
        (2, "补充对话，继续"),
    )
    IS_LIKES = (
        (0, "不点"),
        (1, "点赞"),
        (2, "点踩"),
    )
    STATUS = (
        (0, "正常"),
        (1, "失败"),
    )

    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="会话唯一编号")
    chat_group_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="聊天组唯一编号")
    msg_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="详情编号")
    finish_reason = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="结束原因:length,stop")
    source = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="来源:xcx,pc,h5,android, ios")
    role = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="角色:user,system,assistant")
    size = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="大小：")
    content = models.TextField(blank=True, null=True, default="", verbose_name="内容")
    covert_content = models.TextField(blank=True, null=True, default="", verbose_name="隐性内容")
    content_type = models.CharField(max_length=64, blank=True, null=True, default="text", verbose_name="content类型")
    agent_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="agent_id提示词id")

    origin_image = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="原图")
    total_tokens = models.IntegerField(blank=True, null=True, default=0, verbose_name="聊天总长度")
    completion_tokens = models.IntegerField(blank=True, null=True, default=0, verbose_name="返回长度")
    prompt_tokens = models.IntegerField(blank=True, null=True, default=0, verbose_name="问题长度")
    integral = models.IntegerField(blank=True, null=True, default=0, verbose_name="积分")
    action_type = models.IntegerField(blank=True, null=True, default=1, choices=ACTION_TYPE, verbose_name="行为")
    is_likes = models.IntegerField(blank=True, null=True, default=0, choices=IS_LIKES, verbose_name="点赞行为")
    member_type = models.IntegerField(blank=True, null=True, default=-1,  verbose_name="扣费类型-1免费")
    status = models.IntegerField(blank=True, null=True, default=0,  choices=STATUS, verbose_name="状态")
    is_mod = models.IntegerField(blank=True, null=True, default=0,  verbose_name="是否违规，0否，1是")
    task_id = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="")
    progress = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="进度")
    audio_url = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="音频url")
    images = models.JSONField(verbose_name="图片列表")

    class Meta:
        managed = False
        db_table = 'cc_chat_session_dtl'
        verbose_name = '会话表'
        verbose_name_plural = verbose_name


class DigitalClerkChat(BaseModel):

    session_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="会话唯一编号")
    clerk_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="企业编号")
    company_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="知识库编号")

    class Meta:
        managed = False
        db_table = 'cd_digital_clerk_chat'
        verbose_name = '企业数字员对话中间表'
        verbose_name_plural = verbose_name


class OOpenaiKey(models.Model):
    key = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="")
    server_ip = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")
    o_status = models.IntegerField(blank=True, null=True, default=1, verbose_name="状态1：正常，2：余额不足")
    key_type = models.IntegerField(blank=True, null=True, default=0, verbose_name="")
    desc = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="")

    class Meta:
        managed = False
        db_table = 'oo_openai_key'
        verbose_name = ''
        verbose_name_plural = verbose_name


class CCChatImage(BaseModel):
    CHAT_TYPE = (
        (13, "通义万相"),
    )
    ACTION_TYPE = (
        (3, "文生图"),
        (5, "图文生图"),
        (6, "视频生成"),
    )

    image_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    title = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="标题")
    model = models.CharField(max_length=128, blank=True, null=True, default="", verbose_name="会话模型")
    source = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="来源")
    chat_type = models.IntegerField(blank=True, null=True, default=0, choices=CHAT_TYPE, verbose_name="类型")
    action_type = models.IntegerField(blank=True, null=True, default=3, choices=ACTION_TYPE, verbose_name="行为")
    scenario_type = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="场景类型")

    class Meta:
        managed = False
        db_table = 'cc_chat_image'
        verbose_name = '图片生成历史表'
        verbose_name_plural = verbose_name


class CCChatImageDtl(BaseModel):
    IS_LIKES = (
        (0, "不点"),
        (1, "点赞"),
        (2, "点踩"),
    )
    STATUS = (
        (0, "正常"),
        (1, "失败"),
    )

    image_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="唯一编号")
    msg_code = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="详情编号")
    role = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="角色:user,assistant")
    prompt = models.CharField(max_length=1024, blank=True, null=True, default="", verbose_name="原生提示词")
    prompt_en = models.CharField(max_length=1024, blank=True, null=True, default="", verbose_name="英文提示词")
    negative_prompt = models.CharField(max_length=1024, blank=True, null=True, default="", verbose_name="反向提示词")
    negative_prompt_en = models.CharField(max_length=1024, blank=True, null=True, default="", verbose_name="英文反向提示词")
    covert_prompt = models.CharField(max_length=1024, blank=True, null=True, default="", verbose_name="隐藏提示词")
    style = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="风格")
    transition_style = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="转场风格")
    scene = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="场景类型")
    session_id = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="session_id")
    command = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="命令")
    reason = models.CharField(max_length=512, blank=True, null=True, default="", verbose_name="原因")

    origin_image = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="原图")
    refer_image = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="参考图")
    result_image = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="结果图")
    result_cover = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="结果封面, 视频时存在")

    sampler_index = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="采样器")
    seed = models.IntegerField(blank=True, null=True, default=0, verbose_name="随机种子")
    steps = models.IntegerField(blank=True, null=True, default=0, verbose_name="迭代步数")
    cfg_scale = models.IntegerField(blank=True, null=True, default=0, verbose_name="提示词相关性")

    size = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="大小")
    is_likes = models.IntegerField(blank=True, null=True, default=0, choices=IS_LIKES, verbose_name="点赞行为")
    status = models.IntegerField(blank=True, null=True, default=0,  choices=STATUS, verbose_name="状态")
    is_mod = models.IntegerField(blank=True, null=True, default=0,  verbose_name="是否违规，0否，1是")
    task_id = models.CharField(max_length=256, blank=True, null=True, default="", verbose_name="任务id")
    progress = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="进度")
    quality = models.CharField(max_length=64, blank=True, null=True, default="", verbose_name="质量")
    integral = models.IntegerField(blank=True, null=True, default=0, verbose_name="算力积分")
    change_degree = models.IntegerField(blank=True, null=True, default=1, verbose_name="参考图因子/目标年龄")
    strength = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True, default=0.00, help_text="强度")
    source_similarity = models.CharField(max_length=20, blank=True, null=True, default="1", verbose_name="相似度")

    result_list = models.JSONField(verbose_name="结果列表", default=list)
    file_list = models.JSONField(verbose_name="输入文件列表", default=list)

    class Meta:
        managed = False
        db_table = 'cc_chat_image_dtl'
        verbose_name = '会话表'
        verbose_name_plural = verbose_name


###
class AmModels(models.Model):
    """"""

    out_video = models.CharField(max_length=255, blank=True, null=True, default="", verbose_name="")
    out_video_speak = models.CharField(max_length=255, blank=True, null=True, default="", verbose_name="")
    model_id = models.CharField(max_length=255, blank=True, null=True, default="", verbose_name="")
    status = models.IntegerField(blank=True, null=True, default=0, verbose_name="0: 待生成 1:生成成功")

    class Meta:
        managed = False
        db_table = 'am_models'
        verbose_name = ''
        verbose_name_plural = verbose_name
