#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
ROLE_USER = "user"
ROLE_GUESS = "guess"


Member_Tokens = [2, 3]      # 流量包

CHAT_SCENE = 1  # 场景会话
IMAGE_SCENE = 2     # 场景绘画
TEXT_SCENE = 3     # 其他计算

# 企业知识库状态
ENTERPRISE_SAVE = 1
ENTERPRISE_SUBMIT = 2


FILE_E_CATEGORY = 1     # 企业
FILE_P_CATEGORY = 2     # 项目
FILE_I_CATEGORY = 3     # 资讯
FILE_K_CATEGORY = 4     # 知识库


DEV_PID = 15372
FORMAT_STR = "pcm"

ModelList = [
        "gpt-3.5-turbo",        # 0
        "gpt-4",                # 1
        "gpt-3.5-turbo-16k",    # 2
        "gpt-4-32k"             # 3
    ]

GPT35 = [0, 2]       # 35,绘画,40

GPT40 = [1, 3]

DELL = [15]


GROUP_TYPE = ["4", "5", "8", "10", "12"]


VG_CODE = "1000010006"


EXCHANGE = "ai_exchange"


FILE_CHAT_TYPE = {
    "3": "AsyncBaiDuErnie",     # 百度绘画
    "6": "AsyncMidjourneyImage",     # mj
    "28": "AsyncAliGenerateAnimeVideo",     # 视频人像卡通化
    "29": "AsyncAliGenerateVideoRequest",     # 视频生成
    "30": "AsyncAliEraseVideoLogo",     # 视频去标志
    "31": "AsyncAliEraseVideoSubtitles",     # 视频去字幕
    "36": "AsyncAliReduceVideoNoise",     # 视频去字幕
    "37": "AsyncAliEnhanceVideoQuality",     # 视频增强
    "38": "AsyncAliGenerateVideoCover",     # 视频封面
    "46": "AsyncAliEvaluateVideoQuality",     # 视频评分

    "60": "AsyncVolcengineFaceFusionSubmitTask",   # 视频人脸融合
}


VIDEO_TYPE_TIME_LIST = ["28", "30", "31", "36", "37", "38", "46"]


SPARK_DRAW_HOST = "https://spark-api.cn-huabei-1.xf-yun.com/"
