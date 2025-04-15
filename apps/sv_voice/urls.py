#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.urls import path

from sv_voice.views import text_view, digital_human_views, text_to_speech, voice_train_views, exchange_views


urlpatterns = [
    path("test", text_view.Test.as_view()),

    path("ali_token", text_view.AliToken.as_view()),

    # 语音识别
    path("speech_recognition", text_view.SpeechRecognition.as_view({"get": "list", "post": "create"})),
    path("speech_recognition/<str:speech_code>", text_view.SpeechRecognition.as_view({"put": "update",
                                                                                      "delete": "destroy",
                                                                                      "get": "retrieve"})),

    path("file_identifier", text_view.FileIdentifier.as_view()),
    path("file_identifier_call", text_view.FileIdentifierCall.as_view()),

    # -------------------------------数字人-------------------------------------
    path("digital_human_experience", digital_human_views.DigitalHumanExperienceView.as_view({"post": "create"})),
    path("digital_human_file", digital_human_views.DigitalHumanFileViews.as_view({"post": "create", "get": "list"})),
    path("digital_human_file/<str:file_code>", digital_human_views.DigitalHumanFileViews.as_view({"delete": "destroy"})),

    path("GgetVideoCover", digital_human_views.GgetVideoCover.as_view({"post": "create"})),  # 获取视频封面
    path("my_digital_human", digital_human_views.MyDigitalHumanView.as_view({"get": "list"})),  # 数字人列表
    path("DigitalHumanProjectView", digital_human_views.DigitalHumanProjectList.as_view({"get": "list"})),  # 口播视频项目列表
    path("my_live_video", digital_human_views.MyLiveVideoView.as_view({"get": "list", "put": "update"})),  # 口播视频列表

    # 形象
    path("digital_human_clone", digital_human_views.DigitalHumanClone.as_view({"post": "create"})),  # 创建形象
    path("short_video_digital_human_clone", digital_human_views.ShortVideoDigitalHumanClone.as_view({"post": "create"})),  # 短视频平台创建形象
    path("digital_human_clone/<str:live_code>", digital_human_views.DigitalHumanClone.as_view({
        "get": "retrieve", "put": "update"})),

    # 口播视频
    path("digital_human_project", digital_human_views.DigitalHumanProjectView.as_view({"post": "create",
                                                                                       "delete": "destroy"})),
    path("digital_human_project/<str:project_code>", digital_human_views.DigitalHumanProjectView.as_view({
        "get": "retrieve", "put": "update"})),
    path("get_duration", digital_human_views.DigitalHumanProjectView.as_view({"post": "get_duration"})),  # 声音时长
    path("short_video_get_duration", digital_human_views.DigitalHumanProjectView.as_view({"post": "short_video_get_duration"})),  # 声音时长

    path("get_list_make", digital_human_views.NoAuthDigitalHumanProject.as_view({"post": "get_list_make"})),  # 算法机获取任务
    path("update_human_clone/<str:live_dtl_code>", digital_human_views.NoAuthDigitalHumanProject.as_view({"put": "update"})),

    # 声音克隆
    path("audio_conversion", digital_human_views.AudioConversion.as_view({"post": "create"})),      # 声音转换
    path("customized_voice", digital_human_views.SoundCloneView.as_view({"get": "get_for_voice",
                                                                         "post": "voice_audio_detect"})),
    path("list_customized_voice", digital_human_views.SoundCloneView.as_view({"get": "list_customized_voice"})),
    path("voice_task", digital_human_views.NoAuthSoundCloneView.as_view({"post": "create"})),   # 克隆定时任务
    path("submit_customized_voice", digital_human_views.NoAuthSoundCloneView.as_view({"put": "update"})),   # 训练提交
    # 逻辑
    path("customized_voice_view", digital_human_views.CustomizedVoiceView.as_view({"get": "list", "post": "create"})),
    path("customized_voice_view/<int:pk>", digital_human_views.CustomizedVoiceView.as_view({"get": "retrieve"})),
    # 生成
    path("voice_generate_history", digital_human_views.VoiceGenerateHistoryView.as_view({"get": "list",
                                                                                         "post": "create"})),
    path("no_auth_voice_generate_history", digital_human_views.NoAuthVoiceGenerateHistoryView.as_view({"post": "create"})),


    # -------------------------------文本转语音-------------------------------------
    path("get_speech_engine", text_to_speech.GetSpeechEngine.as_view()),        # 引擎
    path("get_speech_voice", text_to_speech.GetSpeechVoice.as_view()),        # 音色
    path("get_speech_result", text_to_speech.TextToSpeechResult.as_view()),       # 文本转语音结果

    path("text_to_speech", text_to_speech.TextToSpeech.as_view({"get": "list", "post": "create"})),
    path("text_to_speech/<str:h_code>", text_to_speech.TextToSpeech.as_view({"get": "retrieve",
                                                                             "delete": "destroy"})),

    # 火山
    path("VolcengineVoiceTrainTask", voice_train_views.VolcengineVoiceTrainTask.as_view()),     # 训练结果

    path("volcengine_voice_train_pay", voice_train_views.VolcengineVoiceTrainPay.as_view()),
    path("VoiceIdQuery", voice_train_views.VoiceIdQuery.as_view()),         # id余量查询

    path("volcengine_voice_train", voice_train_views.VolcengineVoiceTrain.as_view({
        "get": "list", "post": "create", "put": "once_again_train"
    })),
    path("enable_voice", voice_train_views.VolcengineVoiceTrain.as_view({"put": "enable_voice"})),  # 启用音色
    path("get_vid_number", voice_train_views.VolcengineVoiceTrain.as_view({"get": "get_vid_number"})),  # 获取可用次数


    # -------------------------------卡密兑换-------------------------------------
    path("activate_exchange_tasks", exchange_views.ActivateExchangeTasks.as_view()),
    path("activate_exchange", exchange_views.ActivateExchange.as_view({"get": "list", "post": "create"})),
    path("get_activate_residue_number", exchange_views.ActivateExchange.as_view({"get": "get_activate_residue_number"})),
    path("activate_consume", exchange_views.ActivateConsume.as_view({"get": "list"})),
    path("get_business", exchange_views.GetAdBusiness.as_view()),
]

