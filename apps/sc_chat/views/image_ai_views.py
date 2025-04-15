#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import datetime
import json

import requests
from asgiref.sync import sync_to_async
from django.db import connections, transaction
from django.forms import model_to_dict
from django_redis import get_redis_connection
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.viewsets import ViewSet

from apps.sc_chat.models.chat_models import CCChatSessionDtl, CCChatImage, CCChatImageDtl
from apps.sc_chat.utils import check_members, deduction_calculation, get_dell_model
from language.language_pack import RET
from sc_chat import sqls
from server_chat import settings
from sv_voice.models.exchange_models import DigitalHumanActivateNumber
from utils import image_strategy, constants
from utils.ali_sdk import ali_client
from utils.cst_class import CstResponse
from utils.generate_number import set_flow
from utils.generics import AsyncGenericAPIView
from utils.logical_strategy import OpenaiDall, StableDiffusionImage
from utils.redis_lock import LockRequest
from utils.save_utils import save_image, save_image_v2
from utils.sql_utils import NewSqlMixin, dict_fetchall
from utils.sso_utils import ToOss
from utils.video_utils import get_video_length


class ImageList(NewSqlMixin, APIView):
    query_sql = sqls.IMAGE_LIST_SQL
    sort_field = ["s__create_time"]
    where = " and "

    def set_query_sql(self):
        query_sql = self.query_sql
        title = self.request.query_params.get('title')
        chat_type = self.request.query_params.get('chat_type')
        create_by = self.request.user.user_code
        if title:
            query_sql += f" and title like '{title}%'"
        if create_by:
            query_sql += f" and s.create_by = '{create_by}'"
        if chat_type:
            query_sql += f" and s.chat_type = {chat_type}"
        return query_sql

    def get(self, request, *args, **kwarg):
        """
        会话框列表视图
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


class ImageGenerationView(ViewSet):
    """
    ai图像生成视图 作者：xiaotao 版本号: 文档地址:
    """

    @action(methods=["get"], detail=False)
    def get_baidu_image(self, request, *args, **kwargs):
        user = request.user
        task_id = request.query_params.get("task_id")
        if not task_id:
            return CstResponse(RET.DATE_ERROR)

        dtl_obj = CCChatSessionDtl.objects.filter(task_id=task_id,
                                                  create_by=user.user_code, role="assistant").values(
            "session_code", "chat_group_code", "size", "content", "role", "create_time", "is_mod", "progress", "status")
        for i in dtl_obj:
            if i["create_time"]:
                i["create_time"] = i["create_time"].strftime("%Y-%m-%d %H:%M:%S")
        return CstResponse(RET.OK, data=dtl_obj)


class AsyncDallView(AsyncGenericAPIView):
    """
    ai图像生成视图 作者：xiaotao 版本号: 文档地址:
    """

    # @LockRequest()
    async def post(self, request, *args, **kwargs):
        """
        图像生成
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        user = request.user
        source = user.source
        create_by = user.user_code
        data = request.data
        action_type = data.get("action_type")  # 行为,3:生成图片，4，图片变化,5,图片编辑
        session_code = data.get("session_code")
        chat_group_code = data.get("chat_group_code")
        chat_type = data.get("chat_type") or "2"  # 类型2:dall-e
        image = request.FILES.get("image")  # 图像
        mask = request.FILES.get("mask")  # 面具
        content = data.get("content")
        response_format = data.get("response_format") or ""
        size = data.get("size") or "1024x1024"
        n = int(data.get("n")) or 1

        if action_type not in ["3", "4", "5"]:
            return CstResponse(RET.DATE_ERROR)
        if action_type in ["3", "5"] and not content:
            return CstResponse(RET.DATE_ERROR)
        if action_type == "4" and not image:
            return CstResponse(RET.DATE_ERROR)
        if action_type == "5" and not image:
            return CstResponse(RET.DATE_ERROR)

        _ = check_members(create_by, constants.IMAGE_SCENE, data=data)

        if len(content) < 600:
            _ = ali_client.ali_text_mod(json.dumps({"content": content}, ensure_ascii=False))

        # class_strategy = {
        #     "2": "OpenaiDall",
        # }
        # strategy_obj = getattr(logical_strategy, class_strategy[chat_type])()
        strategy_obj = OpenaiDall()

        file_image = None
        mask_image = None
        if image:
            file_image = image.read()
        if mask:
            mask_image = mask.read()

        data = {
            "prompt": content,
            "n": n,
            "size": size,
            "create_by": create_by,
            "action_type": action_type,
            "response_format": response_format,
            "chat_type": chat_type
        }
        files = {
            "image": file_image,
            "mask": mask_image,
        }
        # print("到达")
        image_urls = await sync_to_async(strategy_obj.asend_data)(data=data, files=files)

        now_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        save_list = [{"role": "user", "url": content}]
        init = ToOss()
        for i in image_urls:
            i["role"] = "assistant"
            # i["url_base"] = "data:image/png;base64," + url_to_base64(i["url"])
            sso_url = init.main("dell_2", img_url=i["url"])
            i["url"] = sso_url
            # i["sso_url"] = settings.NETWORK_STATION + sso_url
            i["sso_url"] = sso_url
            save_list.append(i)

        session_code, chat_group_code = await sync_to_async(save_image)(user, chat_type, session_code,
                                                                        chat_group_code, content, create_by,
                                                                        save_list, action_type, source, size)
        # 响应
        resp = {
            "create_time": now_date,
            "session_code": session_code,
            "chat_group_code": chat_group_code,
            "image_urls": image_urls,
            "chat_type": chat_type,
            "role": "assistant",
            "size": size
        }
        print("11111")
        return CstResponse(RET.OK, data=resp)


class StableDiffusionView(ViewSet):
    """
    sd视图 作者：xiaotao 版本号: 文档地址:
    """

    def create(self, request, *args, **kwargs):

        data = request.data
        user = request.user
        action_type = data.get("action_type")  # 行为,3:生成图片，,5,图片编
        chat_type = data.get("chat_type")  # or "9"
        content = data.get("prompt") or ""
        prompt_en = data.get("prompt_en") or ""

        if not all([content, prompt_en]) or action_type not in ["3", "5"] or not chat_type:
            return CstResponse(RET.DATE_ERROR)
        if action_type == "5" and not data.get("origin_image"):
            return CstResponse(RET.DATE_ERROR, "图文生图模式下图片必传")

        _ = check_members(user.user_code, constants.IMAGE_SCENE, data=data)

        if len(content) < 600:
            _ = ali_client.ali_text_mod(json.dumps({"content": content}, ensure_ascii=False))

        tag = set_flow()
        obj = StableDiffusionImage()

        result = obj.send_data(request, tag=tag)
        return CstResponse(RET.OK, data={"tag": tag})

    @action(methods=["get"], detail=False)
    def get_queue(self, request, *args, **kwargs):
        mq_config = settings.MQ["ty"]
        mq_url = settings.MQ_SERVER
        user = mq_config.get("USER")
        password = mq_config.get("PASSWORD")
        vhost = mq_config.get("vhost")
        sd_query = "sd_query"
        auth = (user, password)
        url = mq_url + f"api/queues/{vhost}/{sd_query}?lengths_age=60&lengths_incr=5&msg_rates_age=60&msg_rates_incr=5&data_rates_age=60&data_rates_incr=5"
        try:
            response = requests.get(url, auth=auth)
        except Exception as e:
            return CstResponse(RET.NO_DATE_ERROR, "队列数获取失败")

        if response.status_code == 200:
            # 解析响应的JSON数据
            data = response.json()
            message_count = data['messages']
        else:
            return CstResponse(RET.NO_DATE_ERROR, "队列数获取失败")
        return CstResponse(RET.OK, data={"message_count": message_count})

    @action(methods=["get"], detail=False)
    def get_sd_model(self, request, *args, **kwargs):
        redis_conn = get_redis_connection('chat')
        # data = [
        #     {
        #         "model_id": 448655425176838,
        #         "name": "sd_xl_base_1.0",
        #         "value": "sd_xl_base_1.0",
        #         "pic_url": "model/8464335e-1b8c-4d7b-9ff1-eb52a357e821.jpg"
        #     },
        #     {
        #         "model_id": 448655598712070,
        #         "name": "sd_xl_refiner_1.0",
        #         "value": "sd_xl_refiner_1.0",
        #         "pic_url": "model/79074d11-6cbd-4054-be37-4ba24c7e03e1.jpg"
        #     },
        #     {
        #         "model_id": 448203980543238,
        #         "name": "亚洲风",
        #         "value": "chilloutmix_NiPrunedFp32Fix",
        #         "pic_url": "model/7a825f3f-0ace-44a8-9c6d-464c54d97d63.jpg"
        #     },
        #     {
        #         "model_id": 448204811220230,
        #         "name": "综合性",
        #         "value": "tangbohu_v11",
        #         "pic_url": "model/6d64a004-0aac-4030-be53-83c8b6aeb202.jpg"
        #     },
        #     {
        #         "model_id": 448205105763590,
        #         "name": "幻想",
        #         "value": "majicMIX fantasy 麦橘幻想_v1.0",
        #         "pic_url": "model/4ffe81d9-c50d-45a7-ab9c-d0a9a20a185b.jpg"
        #     },
        #     {
        #         "model_id": 448205176612102,
        #         "name": "v1-5",
        #         "value": "v1-5-pruned",
        #         "pic_url": "model/892575c6-659f-403f-a733-8e421fa2897c.jpg"
        #     },
        #     {
        #         "model_id": 448205254919430,
        #         "name": "v2-1",
        #         "value": "v2-1_768-ema-pruned",
        #         "pic_url": "model/8177ca4b-18a3-43f0-8d5c-bcfed6a67f1d.jpg"
        #     },
        #     {
        #         "model_id": 448205332997382,
        #         "name": "国风武侠",
        #         "value": "国风武侠Chinese style",
        #         "pic_url": "model/20954c70-ec2d-4c79-a142-dacbc8fc789f.jpg"
        #     },
        #     {
        #         "model_id": 448205424325894,
        #         "name": "亚洲写实",
        #         "value": "亚洲写实",
        #         "pic_url": "model/20af3051-daa7-47b8-98bc-bf8b2635c637.jpg"
        #     },
        #     {
        #         "model_id": 448205497308422,
        #         "name": "博物馆",
        #         "value": "博物馆",
        #         "pic_url": "model/c06885e4-7e69-4461-a1af-5bccd29e0aa6.jpg"
        #     },
        #     {
        #         "model_id": 448205580743942,
        #         "name": "炫酷主题",
        #         "value": "rmadartSD15_v100Test",
        #         "pic_url": "model/8bd1896c-d48f-40b1-b17f-360dec41faa7.jpg"
        #     },
        #     {
        #         "model_id": 448205688485126,
        #         "name": "建筑/室内",
        #         "value": "(设计)建筑 室内dvarch",
        #         "pic_url": "model/e817aad9-fa48-4d73-b4df-5d0a4d411e46.jpg"
        #     }
        #
        #     ]
        # data = json.dumps(data)
        # redis_conn.set("sd_model", data)
        result = json.loads(redis_conn.get("sd_model"))

        return CstResponse(RET.OK, data=result)


class Text2Image(ViewSet):
    chat_type_map = {
        "13": "WanXImage",      # 阿里绘画
        "-13": "WanXImage",      # 阿里绘画
        "14": "VolcengineT2iLdm",   # 火山绘画
        "15": "OpenAiImage",   # openai
        "2000": "SparkDraw",   # 火山绘画

        "16": "VolcengineAllAgeGeneration",   # 人像年龄变化
        "17": "VolcengineFacePretty",   # 智能变美
        "18": "VolcengineJPCartoon",   # 人像漫画
        "19": "VolcengineOCRNormal",   # 文字识别
        "20": "VolcengineHumanSegment",   # 人像抠图
        "21": "VolcengineFaceSwap",   # 人像融合
        "22": "VolcenginePotraitEffect",   # 人像特效
        "23": "VolcengineHairStyle",   # 发型编辑
        "24": "Volcengine3DGameCartoon",   # 3d游戏特效
        "25": "VolcenginePoemMaterial",   # 图片配文
        "26": "VolcengineEmoticonEdit",   # 表情编辑
        "27": "VolcengineEnhancePhotoV2",   # 图像增强
        "32": "AliImitatePhotoStyle",   # 照片修图
        "33": "AliImitateChangeImageSize",   # 照片裁剪
        "34": "AliIImageGenerateDynamic",   # 照片微动
        "35": "AliImageDetectSkinDisease",   # 皮肤病检测
        "39": "AliEnhanceFace",   # 面部修复
        "40": "AliGenerateHumanSketchStyle",   # 人像素描
        "41": "AliLiquifyFace",   # 智能瘦脸
        "42": "AliFaceMakeup",   # 智能美妆
        "43": "AliFaceFilterAdvance",   # 人脸滤镜
        "44": "AliBlurFace",   # 人脸模糊
        "45": "AliRemoveImageSubtitles",   # 图片字幕擦除
        "47": "AliDetectObject",   # 物体识别
        "48": "AliRecognizeFace",   # 面部信息识别
        "49": "AliRemoveImageWatermark",   # 图片标志擦除
        "50": "AliSegmentCommodity",   # 商品抠图
        "51": "AliSegmentBody",   # 人体轮廓分割
        "52": "AliDetectCelebrity",   # 明显识别

        "53": "BaiDuVehicleIdentification",   # 车型识别
        "54": "BaiDuMultiObjectDetect",   # 图像多主体检测
        "55": "BaiDuImageColourize",   # 黑白图像上色
        "56": "BaiDuImageStyleConvert",   # 图像风格转换
        "57": "BaiDuImageDefinitionEnhance",   # 图像清晰度增强
        "58": "AliRunMedQA",   # 智能医学问答
    }

    @LockRequest()
    def create(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        source = user.source
        user_code = user.user_code
        action_type = data.get("action_type")  # 行为,3:生成图片，,5,图片编
        chat_type = data.get("chat_type")  # 13
        a_type = data.get("a_type") or 1  # 类型1算力，2卡密
        model = data.get("model") or ""
        prompt = data.get("prompt")
        data["source"] = source
        data["role"] = "user"
        data["msg_code"] = set_flow()

        if not all([prompt, chat_type, action_type]):
            return CstResponse(RET.DATE_ERROR)
        if chat_type not in self.chat_type_map.keys():
            return CstResponse(RET.DATE_ERROR, "类型错误")

        if a_type == 1:
            _ = check_members(user_code, constants.IMAGE_SCENE, data=data)
        else:
            if not DigitalHumanActivateNumber.objects.filter(create_by=user_code, activate_type_id=4, activate_status=1).exists():
                return CstResponse(RET.NO_NUMBER, "无可用次数，请先兑换卡密")

        if len(prompt) < 600:
            _ = ali_client.ali_text_mod(json.dumps({"content": prompt}, ensure_ascii=False))

        obj = getattr(image_strategy, self.chat_type_map[chat_type])(model=model, chat_type=chat_type)
        request_data = obj.get_data(data, user_code=user_code)

        result = obj.send_data(request_data)

        oss_obj = ToOss()
        result_list = [data]
        rsp = obj.save_result(result, result_list=result_list, oss_obj=oss_obj, data=data)

        for save_result in result_list[1:]:
            if save_result.get("status", 0) != 1:   # 成功才减
                model_c = get_dell_model(data)
                integral = deduction_calculation(chat_type, 1, model_c)
                save_result["integral"] = integral
            save_result["role"] = "assistant"
            save_result["origin_image"] = data.get("origin_image")
        image_code = save_image_v2(data, result_list, user_code)
        resp = {
            "image_code": image_code,
            "results": rsp
        }
        return CstResponse(RET.OK, data=resp)


class AsyncText2Image(ViewSet):
    """
    异步的绘画
    """
    chat_type_map = constants.FILE_CHAT_TYPE

    @LockRequest()
    def create(self, request, *args, **kwargs):
        data = request.data
        user = request.user
        source = user.source
        user_code = user.user_code
        action_type = data.get("action_type")  # 行为,3:生成图片，,5,图片编
        chat_type = data.get("chat_type")  # 13
        model = data.get("model") or ""
        prompt = data.get("prompt")
        data["source"] = source
        data["role"] = "user"
        data["msg_code"] = set_flow()
        data["user_code"] = user_code

        if not all([prompt, chat_type, action_type]):
            return CstResponse(RET.DATE_ERROR)
        if chat_type not in self.chat_type_map.keys():
            return CstResponse(RET.DATE_ERROR, "类型不存在")

        if chat_type in constants.VIDEO_TYPE_TIME_LIST:
            duration = get_video_length(settings.NETWORK_STATION + data.get("origin_image"))
            _ = check_members(user_code, constants.TEXT_SCENE, num=duration, bus_type=chat_type)
        else:
            _ = check_members(user_code, constants.IMAGE_SCENE, data=data)

            if len(prompt) < 600:
                _ = ali_client.ali_text_mod(json.dumps({"content": prompt}, ensure_ascii=False))

        obj = getattr(image_strategy, self.chat_type_map[chat_type])(model=model, chat_type=chat_type)
        request_data = obj.get_data(data, user_code=user_code)

        result = obj.send_data(request_data)

        data.update(result)
        _ = obj.save_result(data)
        return CstResponse(RET.OK, data=result)

    @action(methods=["get"], detail=False)
    def get_image_result(self, request, *args, **kwargs):
        user = request.user
        task_id = request.query_params.get("task_id")
        if not task_id:
            return CstResponse(RET.DATE_ERROR)

        dtl_obj = CCChatImageDtl.objects.filter(task_id=task_id,
                                                create_by=user.user_code, role="assistant").all()
        dtl_list = [model_to_dict(obj) for obj in dtl_obj]
        for i in dtl_list:
            if i["create_time"]:
                i["create_time"] = i["create_time"].strftime("%Y-%m-%d %H:%M:%S")
        return CstResponse(RET.OK, data=dtl_list)


class ChatImageView(ViewSet, NewSqlMixin):
    """

    """
    query_sql = sqls.IMAGE_LIST_SQL2
    sort_field = ["a__create_time"]
    # main_table = "a"
    where = " and "

    def set_query_sql(self):
        query_sql = self.query_sql
        title = self.request.query_params.get('title')
        chat_type = self.request.query_params.get('chat_type')
        create_by = self.request.user.user_code
        query_sql += f" and a.create_by = '{create_by}'"
        if title:
            query_sql += f" and title like '{title}%'"

        if chat_type:
            query_sql += f" and a.chat_type = {chat_type}"
        return query_sql

    def list(self, request, *args, **kwarg):
        """
        会话框列表视图
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

    def retrieve(self, request, image_code, *args, **kwargs):
        """
        会话详情视图
        :param request:
        :param image_code:
        :param args:
        :param kwargs:
        :return:
        """
        user = request.user
        create_by = user.user_code
        sql = sqls.IMAGE_DTL_SQL
        with connections["default"].cursor() as cursor:
            cursor.execute(sql, [image_code, create_by])

            rows = dict_fetchall(cursor)
        return CstResponse(RET.OK, data=rows)

    def destroy(self, request, *args, **kwargs):
        """
        会话删除
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        user = request.user
        create_by = user.user_code
        image_codes = request.data.get("image_codes")

        with transaction.atomic():
            CCChatImage.objects.filter(image_code__in=image_codes, create_by=create_by).update(is_delete=1)
            CCChatImageDtl.objects.filter(image_code__in=image_codes, create_by=create_by).update(is_delete=1)
        return CstResponse(RET.OK)

    @action(methods=["put"], detail=False)
    def image_likes(self, request, *args, **kwargs):
        """
        图片点赞
        """
        data = request.data
        is_likes = data.get("is_likes")  # 行为,0:取消，1：点赞，2：点踩
        msg_code = data.get("msg_code")
        if not all([is_likes, msg_code]):
            return CstResponse(RET.DATE_ERROR)

        CCChatImageDtl.objects.filter(msg_code=msg_code).update(
            is_likes=is_likes
        )

        return CstResponse(RET.OK)
