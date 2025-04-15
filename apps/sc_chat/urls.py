#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.urls import path
from apps.sc_chat.views import gpt_views, image_ai_views, asysc_gpt, translate_text, chat_square_views, openai_views, group_chat
from sc_chat.views import tasks_views

urlpatterns = [
    path('test', gpt_views.Test.as_view()),
    path('GetACToken', gpt_views.GetACToken.as_view()),
    path('webhook', gpt_views.Webhook.as_view()),
    path('chat_session', gpt_views.ChatView.as_view({"get": "list", "delete": "destroy"})),
    path('chat_session/<str:session_code>', gpt_views.ChatView.as_view({"get": "retrieve"})),
    path('chat_session_delete', gpt_views.ChatView.as_view({"delete": "destroy_all"})),     # 删除所有
    path('chat_likes', gpt_views.ChatView.as_view({"put": "chat_likes"})),              # 点赞点踩

    path('update_title', gpt_views.ChatView.as_view({"put": "update_title"})),          # 修改标题

    # ------------------绘图--------------------------------
    path("chat_image", image_ai_views.ChatImageView.as_view({"get": "list", "delete": "destroy",
                                                             "put": "image_likes"})),     # 绘画v2
    path("chat_image/<str:image_code>", image_ai_views.ChatImageView.as_view({"get": "retrieve"})),     # 绘画v2

    path("text_to_image", image_ai_views.Text2Image.as_view({"post": "create"})),  # 同步绘画v2
    path("async_text_to_image", image_ai_views.AsyncText2Image.as_view({"post": "create",
                                                                        "get": "get_image_result"})),  # 异步绘画v2

    path("image_list", image_ai_views.ImageList.as_view()),
    path("async_image_generation", image_ai_views.AsyncDallView.as_view()),
    path("baidu_ernie_image", image_ai_views.ImageGenerationView.as_view({"get": "get_baidu_image"})),

    path("sd_create_image", image_ai_views.StableDiffusionView.as_view({"post": "create"})),
    path("get_queue", image_ai_views.StableDiffusionView.as_view({"get": "get_queue"})),
    path("get_sd_model", image_ai_views.StableDiffusionView.as_view({"get": "get_sd_model"})),


    # ------------------对话--------------------------------
    path("async_chat_send", openai_views.AsyncOpenAiChat.as_view()),        # gpt转发

    path("async_chat_session", asysc_gpt.AsyncChatView.as_view()),
    path("async_chat_completion", asysc_gpt.AsyncChatCompletion.as_view()),

    path("update_session_dtl", asysc_gpt.UpdateSessionDtl.as_view()),


    # ------------------多模型对话--------------------------------
    path("get_model", group_chat.GetModel.as_view()),
    path("chat_role_view", group_chat.ChatRoleView.as_view({"get": "list", "post": "create"})),
    path("chat_role_view/<str:role_code>", group_chat.ChatRoleView.as_view({"put": "update", "get": "retrieve",
                                                                            "delete": "destroy"})),
    path("group_chat", group_chat.GroupChatView.as_view({"get": "list", "post": "create"})),
    path("group_chat/<str:session_code>", group_chat.GroupChatView.as_view({"get": "retrieve", "put": "update",
                                                                            "delete": "destroy"})),

    path("async_group_chat_completion", group_chat.AsyncGroupChatCompletion.as_view()),


    # ------------------翻译--------------------------------
    path("text_translate", translate_text.TextTranslate.as_view()),

    # ------------------问答广场--------------------------------
    path("chat_square", chat_square_views.ChatSquare.as_view({"get": "list", "post": "create"})),
    path("chat_square_rand_list", chat_square_views.ChatSquare.as_view({"get": "rand_list"})),
    path("chat_square/<str:session_code>", chat_square_views.ChatSquare.as_view({"get": "retrieve"})),

    # ------------------定时任务--------------------------------
    path("ErnieAccessToken", tasks_views.ErnieAccessToken.as_view()),
    path("TestChat", tasks_views.TestChat.as_view()),
    path("AliAccessToken", tasks_views.AliAccessToken.as_view()),
]
