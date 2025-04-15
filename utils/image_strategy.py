#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import abc
import base64
import json
import logging
import random
import time
from io import BytesIO

import requests
from PIL import Image
from django_redis import get_redis_connection
from openai import OpenAI
from volcengine.visual.VisualService import VisualService

from language.language_pack import RET
from apps.sc_chat.models.chat_models import AmModels
from server_chat import settings
from utils import constants
from utils.aes_utils import WsParam
from utils.ali_sdk import simple_image_call, ali_client, AliVideoCapacitySdk, ali_video_obj, ali_image_obj, get_suffix, \
    ali_image_analysis, ali_video_cog_obj, ali_face_body_obj, object_det_obj, image_seg_obj
from utils.cst_class import CstException
from utils.exponential_backoff import l_ip, image_exponential_backoff_openai
from utils.generate_number import set_flow
from utils.mq_utils import RabbitMqUtil
from utils.sso_utils import ToOss
from utils.str_utils import url_to_base64, base64_to_binary
from utils.video_utils import get_video_length

logger = logging.getLogger(__name__)
time_out = 60


class ImageStrategy(abc.ABC):
    """

    """

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @abc.abstractmethod
    def get_data(self, data, **kwargs):
        pass

    @abc.abstractmethod
    def send_data(self, data, **kwargs):
        pass

    @abc.abstractmethod
    def save_result(self, response, **kwargs):
        pass


class WanXImage(ImageStrategy):

    def get_data(self, data, **kwargs):
        return data

    def send_data(self, data, **kwargs):
        rsp = simple_image_call(data)
        return rsp

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]

        results = response.output.results
        for result in results:
            url = result.get("url")
            if not url:
                continue
            sso_url = oss_obj.main("wx", img_url=url)
            result["result_image"] = sso_url
            result["msg_code"] = set_flow()
            result_list.append(result)
        return results


class VolcengineT2iLdm(ImageStrategy):
    """火山绘画"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        vg_ak = redis_conn.get("VG_APP_ID")
        vg_sk = redis_conn.get("VG_APP_SECRET")
        self.visual_service = VisualService()
        self.visual_service.set_ak(vg_ak)
        self.visual_service.set_sk(vg_sk)

    def get_data(self, data, **kwargs):
        form = {
            "req_key": "t2i_ldm",
            "text": data.get("prompt"),
            "style_term": data.get("style"),
        }
        return form

    def send_data(self, data, **kwargs):
        model = self.kwargs["model"] or "t2i_ldm"
        try:
            resp = getattr(self.visual_service, model)(data)
        except Exception as e:
            try:
                msg = json.loads(e.args[0][2:-1])
            except Exception as e:
                raise CstException(RET.THIRD_ERROR)
            code = msg.get("code")
            if code in [60102, 60204]:
                raise CstException(RET.THIRD_ERROR, "上传的图片中没有检测到人脸")
            if code == 62600:
                raise CstException(RET.THIRD_ERROR, "上传的图片中人脸数量大于3个")
            raise CstException(RET.THIRD_ERROR, data=msg.get("message"))
        if resp.get("code") != 10000:
            code = resp.get("code")
            if code in [60102, 60204]:
                raise CstException(RET.THIRD_ERROR, "上传的图片中没有检测到人脸")
            if code == 62600:
                raise CstException(RET.THIRD_ERROR, "上传的图片中人脸数量大于3个")
            raise CstException(RET.THIRD_ERROR, resp.get("message"))
        return resp["data"]

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]
        model = self.kwargs["model"] or "t2i_ldm"

        binary_data_list = response.get("binary_data_base64")

        for base_image in binary_data_list:
            result = dict()
            with BytesIO(base64.b64decode(base_image)) as bi:
                sso_url = oss_obj.main(model, file_con=bi)
            result["result_image"] = sso_url
            result["msg_code"] = set_flow()
            result_list.append(result)
        return result_list[1:]


class SparkDraw(ImageStrategy):
    """火山绘画"""
    host = constants.SPARK_DRAW_HOST

    def get_data(self, data, **kwargs):
        data = {
            "header": {
                "app_id": settings.KD_APP_ID,
                "uid": kwargs["user_code"]
            },
            "parameter": {
                "chat": {
                    "domain": "general",
                    "temperature": 0.5,
                    "max_tokens": 4096,
                }
            },
            "payload": {
                "message": {
                    "text": [{
                        "role": "user",
                        "content": data["prompt"]
                    }]
                }
            }
        }
        return data

    def send_data(self, data, **kwargs):
        url = self.host + "v2.1/tti"
        ws_spark = WsParam(settings.KD_APP_ID, settings.KD_API_KEY, settings.KD_API_SECRET, url)
        send_url = ws_spark.create_url(method="POST")
        try:
            rsp = requests.post(send_url, data=json.dumps(data)).json()
        except Exception as e:
            raise CstException(RET.MAX_C_ERR)
        if rsp["header"]["code"] != 0:
            raise CstException(RET.THIRD_ERROR, rsp["header"]["message"])
        return rsp

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]

        base_image = response["payload"]["choices"]["text"][0]["content"]

        result = dict()
        binary_data = base64_to_binary(base_image)

        sso_url = oss_obj.main("spark", file_con=binary_data)
        result["result_image"] = sso_url
        result["msg_code"] = set_flow()
        result_list.append(result)
        return result_list[1:]


class VolcengineAllAgeGeneration(VolcengineT2iLdm):
    """人像年龄变化"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        model = self.kwargs["model"]
        if not all([model, origin_image]):
            raise CstException(RET.DATE_ERROR)
        return {
            "req_key": model,   # all_age_generation
            "image_urls": [settings.NETWORK_STATION + origin_image],
            "target_age": data.get("change_degree") or 5,
        }


class VolcengineFacePretty(VolcengineT2iLdm):
    """智能变美"""

    def get_data(self, data, **kwargs):
        quality = str(data.get("quality"))
        origin_image = data.get("origin_image")
        model = self.kwargs["model"]        # face_pretty
        if not all([model, origin_image, quality]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
            "do_risk": True,
            "multi_face": 1,
            "beauty_level": quality,   # 美颜标准程度
        }

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]
        model = self.kwargs["model"]

        image = response.get("image")

        result = dict()
        with BytesIO(base64.b64decode(image)) as bi:
            sso_url = oss_obj.main(model, file_con=bi)
        result["result_image"] = sso_url
        result["msg_code"] = set_flow()
        result_list.append(result)
        return result_list[1:]


class VolcengineOCRNormal(VolcengineT2iLdm):
    """文字识别"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        model = self.kwargs["model"]  # ocr_normal
        if not all([model, origin_image]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
        }

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]

        line_texts = response.get("line_texts")

        result = dict()
        result["result_list"] = line_texts
        result["msg_code"] = set_flow()
        result_list.append(result)
        return result_list[1:]


class VolcenginePoemMaterial(VolcengineOCRNormal):
    """图片配文"""  # poem_material

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]

        poems = response.get("poems")

        result = dict()
        result["result_list"] = poems
        result["msg_code"] = set_flow()
        result_list.append(result)
        return result_list[1:]


class VolcengineJPCartoon(VolcengineFacePretty):
    """人像漫画"""

    def get_data(self, data, **kwargs):
        style = data.get("style")
        origin_image = data.get("origin_image")
        model = self.kwargs["model"]  # jpcartoon
        if not all([model, origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
            "cartoon_type": style,
            "rotation": 1,
            "do_risk": True,
        }


class VolcengineHumanSegment(VolcengineT2iLdm):
    """人像抠图"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        refer_image = data.get("refer_image")
        quality = data.get("quality") or "1"
        model = self.kwargs["model"]  # human_segment
        if not all([model, origin_image, refer_image]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
            "refine": quality,
            "return_foreground_image": 1,
        }

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]
        model = self.kwargs["model"]
        refer_image = kwargs["data"].get("refer_image")     # 参考图
        result = dict()

        foreground_image = response.get("foreground_image")
        portrait = Image.open(BytesIO(base64.b64decode(foreground_image)))
        try:
            portrait_sp = requests.get(settings.NETWORK_STATION + refer_image).content
        except Exception as e:
            raise CstException(RET.MAX_C_ERR)
        background = Image.open(BytesIO(portrait_sp))

        scale_ratio = min(background.size[0] / portrait.size[0], background.size[1] / portrait.size[1])

        # 缩放人像图像
        scaled_portrait = portrait.resize((int(portrait.size[0] * scale_ratio), int(portrait.size[1] * scale_ratio)),
                                          Image.LANCZOS)

        x = (background.size[0] - scaled_portrait.size[0]) / 2
        y = background.size[1] - scaled_portrait.size[1]

        # 将人像图像放置在背景图像上
        background.paste(scaled_portrait, (int(x), int(y)), scaled_portrait)

        with BytesIO() as image_bytes:
            background.save(image_bytes, format="PNG")
            image_bytes.seek(0)
            sso_url = oss_obj.main(model, file_con=image_bytes)
        result["result_image"] = sso_url
        result["msg_code"] = set_flow()
        result_list.append(result)
        return result_list[1:]


class VolcengineFaceSwap(VolcengineFacePretty):
    """人像融合"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        refer_image = data.get("refer_image")
        change_degree = data.get("change_degree") or "1"
        model = self.kwargs["model"]  # face_swap
        if not all([model, origin_image, refer_image]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + refer_image,
            "template_url": settings.NETWORK_STATION + origin_image,
            "action_id": "faceswap",
            "version": 2.0,
            "source_similarity": change_degree
        }


class VolcenginePotraitEffect(VolcengineFacePretty):
    """人像特效"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")
        model = self.kwargs["model"]  # potrait_effect
        if not all([model, origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
            "type": style,
            "return_type": 0,
        }


class VolcengineHairStyle(VolcengineFacePretty):
    """发型编辑"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")
        model = self.kwargs["model"]  # hair_style
        if not all([model, origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
            "hair_type": style,
            "do_risk": True,
        }


class VolcengineEmoticonEdit(VolcengineFacePretty):
    """表情编辑"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")
        model = self.kwargs["model"]  # emoticon_edit
        if not all([model, origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
            "service_choice": style,
            "do_risk": True,
        }


class Volcengine3DGameCartoon(VolcengineFacePretty):
    """3d游戏特效"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        model = self.kwargs["model"]  # three_d_game_cartoon
        if not all([model, origin_image]):
            raise CstException(RET.DATE_ERROR)
        return {
            "image_url": settings.NETWORK_STATION + origin_image,
        }


class VolcengineEnhancePhotoV2(VolcengineT2iLdm):
    """图像增强"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        size = data.get("size")
        model = self.kwargs["model"]        # enhance_photo_v2
        if not all([model, origin_image, size]):
            raise CstException(RET.DATE_ERROR)
        return {
            "req_key": "lens_lqir",
            "image_urls": [settings.NETWORK_STATION + origin_image],
            "resolution_boundary": size,
            "enable_hdr": True,
            "enable_wb": True,
            "result_format": 0,
            "jpg_quality": 95,   # 值越高，代表生成jpg图片的质量越高
            "hdr_strength": 1.0,   # 值越高，代表HDR效果越明显
        }


class OpenAiImage(ImageStrategy):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        model = kwargs["model"] or "dall-e-3"
        redis_conn = get_redis_connection('config')
        key = f"dell_key_{l_ip}"
        api_base_key = f"api_base_{model}"
        api_key = redis_conn.get(key)
        if not api_key:
            raise CstException(RET.KEY_ERR, "key未配置，请联系客服配置")
        api_base = redis_conn.get(api_base_key) or None
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_base,
            timeout=60,
        )

    def get_data(self, data, **kwargs):
        model = self.kwargs["model"] or "dall-e-3"
        user = kwargs["user_code"]
        quality = data.get("quality") or "standard"
        request_data = {
            "model": model,
            "prompt": data.get("prompt"),
            "size": data.get("size"),
            "quality": quality,
            "style": data.get("style"),     # vivid,natural
            "n": data.get("n") or 1,
            "user": user,
        }
        return request_data

    @image_exponential_backoff_openai
    def send_data(self, data, **kwargs):

        response = self.client.images.generate(**data)
        return response.data

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]

        for image in response:
            resp_dict = dict()
            img_url = image.url
            sso_url = oss_obj.main("dell3", img_url=img_url)
            try:
                mod_url = settings.NETWORK_STATION + sso_url
                _ = ali_client.ali_image_mod(mod_url)
            except CstException as e:
                oss_obj.delete_object(sso_url)
                raise CstException(e.code, e.message)

            resp_dict["result_image"] = sso_url
            resp_dict["covert_prompt"] = image.revised_prompt
            resp_dict["msg_code"] = set_flow()
            result_list.append(resp_dict)

        return result_list[1:]


class AliImitatePhotoStyle(ImageStrategy):
    """阿里照片修图"""
    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        refer_image = data.get("refer_image")
        if not all([origin_image, refer_image]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        refer_image = settings.NETWORK_STATION + data["refer_image"]
        rsp = ali_image_obj.imitate_photo_style(origin_image, refer_image)
        return rsp

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]

        resp_dict = dict()
        img_url = response.image_url
        suffix = get_suffix(img_url)
        sso_url = oss_obj.main("ali_image", img_url=img_url, file_extension=suffix)

        resp_dict["result_image"] = sso_url
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class AliImitateChangeImageSize(ImageStrategy):
    """阿里图像裁剪"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        size = data.get("size")
        if not all([origin_image, size]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        size = data["size"]
        size = size.split("*")
        rsp = ali_image_obj.change_image_size(size[0], size[1], origin_image)
        return rsp

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]

        resp_dict = dict()
        img_url = response.url
        suffix = get_suffix(img_url)
        sso_url = oss_obj.main("ali_image", img_url=img_url, file_extension=suffix)

        resp_dict["result_image"] = sso_url
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class AliRemoveImageSubtitles(ImageStrategy):
    """图片字幕擦除"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        if not all([origin_image]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_image_obj.remove_image_subtitles(origin_image)
        return rsp

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]

        resp_dict = dict()
        img_url = response.image_url
        suffix = get_suffix(img_url)
        sso_url = oss_obj.main("ali_image", img_url=img_url, file_extension=suffix)

        resp_dict["result_image"] = sso_url
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class AliRemoveImageWatermark(AliRemoveImageSubtitles):
    """图片标志擦除"""
    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_image_obj.remove_image_watermark(origin_image)
        return rsp


class AliImageDetectSkinDisease(ImageStrategy):
    """阿里皮肤检测"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        if not all([origin_image]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_image_analysis.detect_skin_disease(origin_image)
        return rsp

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]

        resp_dict = dict()

        resp_dict["result_list"] = response.results
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class AliRunMedQA(ImageStrategy):
    """智能医学问答"""

    def get_data(self, data, **kwargs):
        file_list = data.get("file_list")
        style = data.get("style")
        if not all([file_list, style]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        session_id = data.get("session_id")
        rsp = ali_image_analysis.run_med(data["style"], session_id, data["file_list"], data["prompt"])
        return rsp

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]
        data = kwargs["data"]
        session_id = data.get("session_id")

        resp_dict = dict()
        resp_dict["result_list"] = response.to_map()
        resp_dict["msg_code"] = set_flow()
        resp_dict["session_id"] = session_id
        result_list.append(resp_dict)

        return result_list[1:]


class AliEnhanceFace(AliImageDetectSkinDisease):
    """面部修复增强"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.enhance_face_options(origin_image)
        return rsp

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]
        oss_obj = kwargs["oss_obj"]

        img_url = response.data.image_url
        suffix = get_suffix(img_url)
        sso_url = oss_obj.main("ali_image", img_url=img_url, file_extension=suffix)

        resp_dict = dict()
        resp_dict["result_image"] = sso_url
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class AliDetectObject(AliImageDetectSkinDisease):
    """物体识别"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = object_det_obj.detect_object(origin_image)
        return rsp

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]

        save_data = []
        result_data = response.data.elements
        for r in result_data:
            r_dict = dict()
            r_dict["boxes"] = r.boxes
            r_dict["score"] = r.score
            r_dict["type"] = r.type
            save_data.append(r_dict)

        resp_dict = dict()
        resp_dict["result_list"] = save_data
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class AliRecognizeFace(AliImageDetectSkinDisease):
    """人脸信息识别"""
    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.recognize_face(origin_image)
        return rsp

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]
        save_data = dict()
        result_data = response.data
        save_data["gender_list"] = result_data.gender_list
        save_data["face_count"] = result_data.face_count
        save_data["expressions"] = result_data.expressions
        save_data["hat_list"] = result_data.hat_list
        save_data["face_probability_list"] = result_data.face_probability_list
        save_data["glasses"] = result_data.glasses
        save_data["masks"] = result_data.masks
        save_data["age_list"] = result_data.age_list

        resp_dict = dict()
        resp_dict["result_list"] = save_data
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)
        return result_list[1:]


class AliDetectCelebrity(AliImageDetectSkinDisease):
    """明显识别"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.detect_celebrity(origin_image)
        return rsp


class AliGenerateHumanSketchStyle(AliEnhanceFace):
    """人像素描"""
    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")       # ["head", "full"]
        if not all([origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.generate_human_sketch_style(origin_image, data["style"])
        return rsp


class AliLiquifyFace(AliGenerateHumanSketchStyle):
    """智能瘦脸"""
    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.liquify_face(origin_image, data["style"])
        return rsp


class AliSegmentCommodity(AliGenerateHumanSketchStyle):
    """商品抠图/分割"""
    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        if not all([origin_image]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = image_seg_obj.segment_commodity(origin_image, data.get("style"))
        return rsp


class AliSegmentBody(AliSegmentCommodity):
    """人体轮廓分割"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = image_seg_obj.segment_body(origin_image, data.get("style"))
        return rsp


class AliFaceMakeup(AliEnhanceFace):
    """智能美妆"""
    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")       # 0-6
        strength = str(data.get("strength") or "")       # 0-1
        if not all([origin_image, style, strength]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.face_makeup(origin_image, data["style"], data["strength"])
        return rsp


class AliFaceFilterAdvance(AliFaceMakeup):
    """人脸滤镜"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.face_filter(origin_image, data["style"], data["strength"])
        return rsp


class AliBlurFace(AliEnhanceFace):
    """人像脱敏/模糊"""
    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        rsp = ali_face_body_obj.blur_face(origin_image)
        return rsp


class AliIImageGenerateDynamic(ImageStrategy):
    """阿里图像微动"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")
        if not all([origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        style = data["style"]
        rsp = ali_image_obj.generate_dynamic_image(origin_image, style)
        return rsp

    def save_result(self, response, **kwargs):
        oss_obj = kwargs["oss_obj"]
        result_list = kwargs["result_list"]

        resp_dict = dict()
        img_url = response.url
        suffix = get_suffix(img_url)
        sso_url = oss_obj.main("ali_image", img_url=img_url, file_extension=suffix)

        resp_dict["result_image"] = sso_url
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class BaiDuVehicleIdentification(ImageStrategy):
    """车型识别"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.realm_name = settings.EB_HOST
        redis_conn = get_redis_connection('config')
        self.access_token = redis_conn.get("baidu_ernie")

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        if not all([origin_image]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        request_url = self.realm_name + "rest/2.0/image-classify/v1/car" + f"?access_token={self.access_token}"
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"url": origin_image, "top_num": 5, "baike_num": 0}
        response = self.request_send(request_url, params, headers)
        return response

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]

        resp_dict = dict()
        resp_dict["result_list"] = response
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]

    def request_send(self, request_url, params, headers):
        try:
            response = requests.post(request_url, data=params, headers=headers).json()
        except Exception as e:
            raise CstException(RET.DATE_ERROR)
        if response.get("error_code"):
            raise CstException(RET.SERVER_ERROR, response.get("error_msg"))
        return response


class BaiDuMultiObjectDetect(BaiDuVehicleIdentification):
    """图像主体检测"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        request_url = self.realm_name + "rest/2.0/image-classify/v1/multi_object_detect" + f"?access_token={self.access_token}"
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"url": origin_image}
        response = self.request_send(request_url, params, headers)
        return response

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]

        resp_dict = dict()
        resp_dict["result_list"] = response["result"]
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class BaiDuImageColourize(BaiDuVehicleIdentification):
    """黑白图像上色"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        request_url = self.realm_name + "rest/2.0/image-process/v1/colourize" + f"?access_token={self.access_token}"
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"url": origin_image}
        response = self.request_send(request_url, params, headers)
        return response

    def save_result(self, response, **kwargs):
        result_list = kwargs["result_list"]
        oss_obj = kwargs["oss_obj"]
        data = kwargs["data"]
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        image = response["image"]
        binary_data = base64_to_binary(image)

        suffix = get_suffix(origin_image)
        sso_url = oss_obj.main("ali_image", file_con=binary_data, file_extension=suffix)

        resp_dict = dict()
        resp_dict["result_image"] = sso_url
        resp_dict["msg_code"] = set_flow()
        result_list.append(resp_dict)

        return result_list[1:]


class BaiDuImageDefinitionEnhance(BaiDuImageColourize):
    """图像清晰度增强"""

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        request_url = self.realm_name + "rest/2.0/image-process/v1/image_definition_enhance" + f"?access_token={self.access_token}"
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"url": origin_image}
        response = self.request_send(request_url, params, headers)
        return response


class BaiDuImageStyleConvert(BaiDuImageColourize):
    """图像风格转换"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")
        if not all([origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        origin_image = settings.NETWORK_STATION + data["origin_image"]
        request_url = self.realm_name + "rest/2.0/image-process/v1/style_trans" + f"?access_token={self.access_token}"
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        params = {"url": origin_image, "option": data["style"]}
        response = self.request_send(request_url, params, headers)
        return response


# ------------------------------------------------------------------------------------
# 异步
# ------------------------------------------------------------------------------------


class AsyncImageStrategy(ImageStrategy):
    rabbit_mq = RabbitMqUtil()
    oss_obj = ToOss()

    def get_data(self, data, **kwargs):
        pass

    def send_data(self, data, **kwargs):
        pass

    def save_result(self, response, **kwargs):
        data = {
            'exchange': "image_exchange",
            'queue': "image_query",
            'routing_key': 'image_generate',
            'type': "direct",
            "msg": response
        }
        self.rabbit_mq.send_handle(data)
        return

    @abc.abstractmethod
    def result_query(self, data, result_list, **kwargs):
        """任务查询"""
        pass


class AsyncVolcengineFaceFusionSubmitTask(AsyncImageStrategy):
    """
    火山视频人脸融合
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        vg_ak = redis_conn.get("VG_APP_ID")
        vg_sk = redis_conn.get("VG_APP_SECRET")
        self.visual_service = VisualService()
        self.visual_service.set_ak(vg_ak)
        self.visual_service.set_sk(vg_sk)

    def get_data(self, data, **kwargs):
        session_id = data.get("session_id")
        origin_image = data.get("origin_image")
        refer_image = data.get("refer_image")
        style = data.get("style")
        if not all([session_id, origin_image, refer_image, style]):
            raise CstException(RET.DATE_ERROR)
        form = {
            "req_key": "facefusionmovie_standard",
            "image_url": settings.NETWORK_STATION + origin_image,        # 原图
            "video_url": settings.NETWORK_STATION + refer_image,   # 视频
            "source_similarity": data.get("source_similarity") or 1,
        }
        return form

    def send_data(self, data, **kwargs):
        model = self.kwargs["model"] or "face_fusion_movie_submit_task"
        for i in range(3):
            try:
                resp = getattr(self.visual_service, model)(data)
            except Exception as e:
                if i == 2:
                    try:
                        msg = json.loads(e.args[0][2:-1])
                    except Exception as e:
                        raise CstException(RET.THIRD_ERROR)
                    code = msg.get("code")
                    if code in [60102, 60204]:
                        raise CstException(RET.THIRD_ERROR, "上传的文件中没有检测到人脸")
                    raise CstException(RET.THIRD_ERROR, data=msg.get("message"))
                time_to_sleep = random.uniform(1, 2)
                time.sleep(time_to_sleep)
                continue
            if resp.get("code") != 10000:
                code = resp.get("code")
                if code in [60102, 60204]:
                    raise CstException(RET.THIRD_ERROR, "上传的文件中没有检测到人脸")
                raise CstException(RET.THIRD_ERROR, resp.get("message"))
            return resp["data"]

    def result_query(self, data, result_list, **kwargs):
        session_id = data["session_id"]
        style = data["style"]
        req_data = {
            "req_key": "facefusionmovie_standard",
            "task_id": data["task_id"]
        }
        model = "face_fusion_movie_get_result"
        number = "0"
        for num in range(300):
            if num == 299:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = getattr(self.visual_service, model)(req_data)
                print(result)
            except Exception as e:
                if num == 6:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
                # self.up_am(session_id)
                # result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                # break
            if result.get("code") != 10000:
                self.up_am(session_id)
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow(), "reason": result.get("message")})
                break
            rsp_data = result["data"]
            status = rsp_data.get("status") or ""
            if status == "done":
                s_result = json.loads(rsp_data["resp_data"])
                video_url = s_result.get("video_url")
                sso_url = self.oss_obj.main("volcengine_video", img_url=video_url, file_extension="mp4")
                # print(sso_url)
                result_dict = dict()
                result_dict["result_image"] = sso_url
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = data["task_id"]
                result_list.append(result_dict)
                up_dict = {
                    "status": 1,
                }
                if style == "1":
                    up_dict["out_video"] = sso_url
                else:
                    up_dict["out_video_speak"] = sso_url
                AmModels.objects.filter(model_id=session_id).update(**up_dict)
                # number = get_video_length(settings.NETWORK_STATION + sso_url)
                break
            elif status in ["in_queue", "generating"]:
                time_to_sleep = random.uniform(2, 6)
                time.sleep(time_to_sleep)
            else:
                self.up_am(session_id)
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                break
        return number

    @staticmethod
    def up_am(session_id):
        AmModels.objects.filter(model_id=session_id).update(status=2)


class AsyncBaiDuErnie(AsyncImageStrategy):
    """百度绘画"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.realm_name = settings.EB_HOST
        redis_conn = get_redis_connection('config')
        self.access_token = redis_conn.get("baidu_ernie")

    def get_data(self, data, **kwargs):
        model = self.kwargs["model"] or "txt2img"   # txt2imgv2
        if model == "txt2img":
            req_data = {
                "text": data.get("prompt"),
                "style": data.get("style"),
                "resolution": data.get("size"),
                "num": data.get("n") or 1,
            }
        else:
            size = data.get("size") or "1024*1024"
            size = size.split("*")
            change_degree = data.get("change_degree") or 1
            req_data = {
                "prompt": data["prompt"],
                "width": int(size[0]),
                "height": int(size[1]),
                "image_num": data.get("n") or 1,
                "url": settings.NETWORK_STATION + data.get("origin_image"),
                "change_degree": change_degree,
            }
        return json.dumps(req_data, ensure_ascii=True)

    def send_data(self, data, **kwargs):
        model = self.kwargs["model"] or "txt2img"
        url = self.realm_name + f"rpc/2.0/ernievilg/v1/{model}?access_token={self.access_token}"
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        try:
            result = requests.post(url, data=data, headers=headers, timeout=time_out)
            result = result.json()
        except Exception as e:
            raise CstException(RET.SERVER_ERROR, str(e))
        if result.get("error_code"):
            raise CstException(RET.SERVER_ERROR, result.get("error_msg"))
        if model == "txt2img":
            return {"task_id": result["data"]["taskId"]}
        return result["data"]

    def result_query(self, data, result_list, **kwargs):
        task_id = data["task_id"]
        model = data.get("model") or "txt2img"
        if model == "txt2img":
            query_model = "getImg"
            data = {
                "taskId": task_id
            }
        else:
            query_model = "getImgv2"
            data = {
                "task_id": task_id
            }

        url = self.realm_name + f"rpc/2.0/ernievilg/v1/{query_model}?access_token={self.access_token}"
        for num in range(200):
            if num == 199:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = requests.post(url, data=json.dumps(data), timeout=time_out)
                result = result.json()
                # print(result)
                if result.get("error_code"):
                    logger.error(f"""ernie_query---{result}""")
                    raise Exception("错误---")
            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
            if model == "txt2img":
                rsp_data = result.get("data")
                status = rsp_data.get("status")
                img_urls = rsp_data.get("imgUrls")
                if status == 1:
                    for i in img_urls:
                        b_url = i.pop("image", "")
                        sso_url = self.oss_obj.main("ernie", img_url=b_url)
                        i["result_image"] = sso_url
                        i["msg_code"] = set_flow()
                        i["task_id"] = task_id
                        result_list.append(i)
                    break
            else:
                rsp_data = result.get("data")
                task_status = rsp_data.get("task_status")
                task_progress = rsp_data.get("task_progress")
                sub_task_result_list = rsp_data.get("sub_task_result_list")
                if task_status == "SUCCESS" and task_progress == 1:
                    for i in sub_task_result_list:
                        final_image_list = i["final_image_list"]
                        for im in final_image_list:
                            b_url = im.pop("img_url", "")
                            sso_url = self.oss_obj.main("ernie", img_url=b_url)
                            im["result_image"] = sso_url
                            im["msg_code"] = set_flow()
                            im["task_id"] = task_id
                            result_list.append(im)
                    break
                elif task_status == "FAILED":
                    result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                    break
            time.sleep(2)

        return "1"    # 现在 是生成1张


class AsyncMidjourneyImage(AsyncImageStrategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        redis_conn = get_redis_connection('config')
        self.mj_base = redis_conn.get("mj_base")
        self.mj_key = redis_conn.get("mj_key")
        self.call_back_host = settings.CALLBACK

    def get_headers(self):
        headers = {
            'Authorization': f'Bearer {self.mj_key}',
            'User-Agent': 'Apifox/1.0.0 (https://apifox.com)',
            'Content-Type': 'application/json'
        }
        return headers

    def get_data(self, data, **kwargs):
        file_list = data.get("file_list", [])
        prompt_en = data.get("prompt_en")
        if not prompt_en:
            raise CstException(RET.DATE_ERROR)
        base64_array = []
        for image in file_list:
            image_url = settings.NETWORK_STATION + image
            base64_array.append("data:image/png;base64," + url_to_base64(image_url))
        command = ""
        size = data.get("size")
        if size:
            command += f" --ar {size}"
        command += " --v 5 --q 2"
        prompt_en += command

        data = {
            "state": command,
            "prompt": prompt_en,    # 英文提示词
            # "notifyHook": self.call_back_host + "api/chat/mj_call_back",
            "notifyHook": "",
            "base64Array": base64_array,
        }
        return data

    def send_data(self, data, **kwargs):
        headers = self.get_headers()

        url = self.mj_base + "mj/submit/imagine"
        try:
            rsp = requests.post(url, data=json.dumps(data), headers=headers).json()
        except Exception as e:
            raise CstException(RET.SERVER_ERROR, str(e))
        if rsp.get("code") not in [1, 22]:
            raise CstException(RET.MAX_C_ERR, rsp.get("description"))
        return {"task_id": rsp["result"]}

    def result_query(self, data, result_list, **kwargs):
        headers = self.get_headers()

        url = self.mj_base + f"mj/task/{data['task_id']}/fetch"
        for num in range(200):
            if num == 199:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                rsp = requests.get(url, params="", headers=headers).json()

            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
            # print(rsp)
            task_status = rsp.get("status")
            if task_status == "SUCCESS":
                video_url = rsp.get("imageUrl")
                sso_url = self.oss_obj.main("mj_image", img_url=video_url)
                result_dict = dict()
                result_dict["result_image"] = sso_url
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = data["task_id"]
                result_list.append(result_dict)
                break
            elif task_status == "FAILED":
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow(), "reason": rsp.get("failReason")})
                break
            else:
                time.sleep(2)
        return "1"


class AsyncAliGenerateAnimeVideo(AsyncImageStrategy):
    """视频人像卡通化"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        file_extension = data.get("file_extension")
        style = data.get("style")
        if not all([origin_image, style, file_extension]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        video_url = settings.NETWORK_STATION + data["origin_image"]
        result = ali_video_obj.generate_anime_video(video_url, data["style"])
        # print(result)
        return {"task_id": result.request_id}

    def result_query(self, data, result_list, **kwargs):
        task_id = data["task_id"]
        file_extension = data["file_extension"]
        number = "0"
        for num in range(300):
            if num == 299:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = ali_video_obj.get_async_job_result(task_id)
            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
            # print(type(result.data), result.data)
            status = result.data.status
            if status == "PROCESS_SUCCESS":
                s_result = json.loads(result.data.result)
                video_url = s_result.get("videoUrl")
                sso_url = self.oss_obj.main("ali_video", img_url=video_url, file_extension=file_extension)
                result_dict = dict()
                result_dict["result_image"] = sso_url
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = task_id
                result_list.append(result_dict)
                number = get_video_length(settings.NETWORK_STATION + sso_url)
                # print(duration)
                break
            elif status in ["QUEUING", "PROCESSING"]:
                time.sleep(2)
            else:
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                break
        return number


class AsyncAliGenerateVideoRequest(AsyncImageStrategy):
    """生成视频"""

    def get_data(self, data, **kwargs):
        file_list = data.get("file_list")
        # size = data.get("size")
        style = data.get("style")
        if not all([file_list, style]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        file_list = data["file_list"]
        style = data["style"]
        size = data.get("size")
        transition_style = data.get("transition_style") or None
        scene = data.get("scene") or "general"
        if size:
            size_list = size.split("*")
        else:
            size_list = [None,  None]
        result = ali_video_obj.generate_video_create(file_list, size_list[0], size_list[1], style, transition_style, scene)
        # print(result)
        return {"task_id": result.request_id}

    def result_query(self, data, result_list, **kwargs):
        task_id = data["task_id"]
        number = "0"
        for num in range(300):
            if num == 299:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = ali_video_obj.get_async_job_result(task_id)
            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue

            status = result.data.status
            if status == "PROCESS_SUCCESS":
                s_result = json.loads(result.data.result)
                # print(s_result)
                result_cover = s_result.get("VideoCoverUrl")
                video_url = s_result.get("VideoUrl")
                sso_url = self.oss_obj.main("ali_video", img_url=video_url, file_extension="mp4")
                sso_result_cover = self.oss_obj.main("ali_video", img_url=result_cover, file_extension="jpg")
                result_dict = dict()
                result_dict["result_image"] = sso_url
                result_dict["result_cover"] = sso_result_cover
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = task_id
                result_list.append(result_dict)
                number = get_video_length(settings.NETWORK_STATION + sso_url)
                # print(duration)
                break
            elif status in ["QUEUING", "PROCESSING"]:
                time.sleep(2)
            else:
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                break
        return number


class AsyncAliEraseVideoLogo(AsyncImageStrategy):
    """视频去标志"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        if not all([origin_image]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        video_url = settings.NETWORK_STATION + data["origin_image"]
        result = ali_video_obj.erase_video_logo(video_url)
        # print(result)
        return {"task_id": result.request_id}

    def result_query(self, data, result_list, **kwargs):
        task_id = data["task_id"]
        mq_obj = kwargs["mq_obj"]
        file_extension = data.get("file_extension") or "mp4"
        number = "0"
        for num in range(200):
            if num == 199:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = ali_video_obj.get_async_job_result(task_id)
            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
            # print(type(result.data), result.data)
            status = result.data.status
            if status == "PROCESS_SUCCESS":
                s_result = json.loads(result.data.result)
                # print(s_result)
                video_url = s_result.get("VideoUrl")
                sso_url = self.oss_obj.main("ali_video", img_url=video_url, file_extension=file_extension)
                result_dict = dict()
                result_dict["result_image"] = sso_url
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = task_id
                result_list.append(result_dict)
                number = get_video_length(settings.NETWORK_STATION + sso_url)
                # print(duration)
                break
            elif status in ["QUEUING", "PROCESSING"]:
                time.sleep(5)
                mq_obj.connection.process_data_events()
            else:
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                break
        return number


class AsyncAliEraseVideoSubtitles(AsyncAliEraseVideoLogo):
    """视频去字慕"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        if not all([origin_image]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        video_url = settings.NETWORK_STATION + data["origin_image"]
        result = ali_video_obj.erase_video_subtitles(video_url)
        return {"task_id": result.request_id}


class AsyncAliReduceVideoNoise(AsyncAliEraseVideoLogo):
    """视频降噪"""

    def send_data(self, data, **kwargs):
        video_url = settings.NETWORK_STATION + data["origin_image"]
        result = ali_video_obj.reduce_video_noise(video_url)
        return {"task_id": result.request_id}

    def result_query(self, data, result_list, **kwargs):
        task_id = data["task_id"]
        mq_obj = kwargs["mq_obj"]
        number = "0"
        for num in range(200):
            if num == 199:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = ali_video_obj.get_async_job_result(task_id)
            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
            # print(type(result.data), result.data)
            status = result.data.status
            if status == "PROCESS_SUCCESS":
                s_result = json.loads(result.data.result)
                video_url = s_result.get("videoUrl")
                suffix = get_suffix(video_url)
                sso_url = self.oss_obj.main("ali_video", img_url=video_url, file_extension=suffix)
                result_dict = dict()
                result_dict["result_image"] = sso_url
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = task_id
                result_list.append(result_dict)
                number = get_video_length(settings.NETWORK_STATION + sso_url)
                # print(duration)
                break
            elif status in ["QUEUING", "PROCESSING"]:
                time.sleep(10)
                mq_obj.connection.process_data_events()
            else:
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                break
        return number


class AsyncAliEnhanceVideoQuality(AsyncAliReduceVideoNoise):
    """视频增强"""

    def send_data(self, data, **kwargs):
        video_url = settings.NETWORK_STATION + data["origin_image"]
        result = ali_video_obj.enhance_video_quality(video_url)
        return {"task_id": result.request_id}


class AsyncAliGenerateVideoCover(AsyncImageStrategy):
    """视频封面"""

    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        style = data.get("style")
        if not all([origin_image, style]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        video_url = settings.NETWORK_STATION + data["origin_image"]
        is_gif = True if data["style"] == "True" else False
        result = ali_video_cog_obj.generate_video_cover(video_url, is_gif)
        return {"task_id": result.request_id}

    def result_query(self, data, result_list, **kwargs):
        task_id = data["task_id"]
        mq_obj = kwargs["mq_obj"]
        number = "0"
        for num in range(200):
            if num == 199:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = ali_video_obj.get_async_job_result(task_id)
            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
            # print(type(result.data), result.data)
            status = result.data.status
            if status == "PROCESS_SUCCESS":
                s_result = json.loads(result.data.result)
                origin_image = result_list[0]["origin_image"]
                # print(s_result)
                outputs = s_result.get("Outputs")
                out_list = []
                for out in outputs:
                    video_url = out["ImageURL"]
                    suffix = get_suffix(video_url)
                    sso_url = self.oss_obj.main("ali_video", img_url=video_url, file_extension=suffix)
                    out_list.append(sso_url)
                result_dict = dict()
                result_dict["result_list"] = out_list
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = task_id
                result_list.append(result_dict)
                number = get_video_length(settings.NETWORK_STATION + origin_image)
                # print(duration)
                break
            elif status in ["QUEUING", "PROCESSING"]:
                time.sleep(10)
                mq_obj.connection.process_data_events()
            else:
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                break
        return number


class AsyncAliEvaluateVideoQuality(AsyncImageStrategy):
    """视频画质评估"""
    def get_data(self, data, **kwargs):
        origin_image = data.get("origin_image")
        model = data.get("model")
        if not all([origin_image, model]):
            raise CstException(RET.DATE_ERROR)
        return data

    def send_data(self, data, **kwargs):
        video_url = settings.NETWORK_STATION + data["origin_image"]
        result = ali_video_cog_obj.evaluate_video_quality(video_url, data["model"])
        return {"task_id": result.request_id}

    def result_query(self, data, result_list, **kwargs):
        task_id = data["task_id"]
        mq_obj = kwargs["mq_obj"]
        number = "0"
        for num in range(200):
            if num == 199:
                raise CstException(RET.MAX_RETRY_ERROR)
            try:
                result = ali_video_obj.get_async_job_result(task_id)
            except Exception as e:
                if num == 3:
                    raise CstException(RET.MAX_RETRY_ERROR)
                time.sleep(2)
                continue
            # print(type(result.data), result.data)
            status = result.data.status
            if status == "PROCESS_SUCCESS":
                s_result = json.loads(result.data.result)
                origin_image = result_list[0]["origin_image"]
                # print(s_result)
                json_url = s_result.get("jsonUrl")
                suffix = get_suffix(json_url)
                json_url = self.oss_obj.main("ali_video", img_url=json_url, file_extension=suffix)
                s_result["jsonUrl"] = json_url
                pdf_url = s_result.get("pdfUrl")
                suffix = get_suffix(json_url)
                pdf_url = self.oss_obj.main("ali_video", img_url=pdf_url, file_extension=suffix)
                s_result["pdfUrl"] = pdf_url
                result_dict = dict()
                result_dict["result_list"] = [s_result]
                result_dict["msg_code"] = set_flow()
                result_dict["task_id"] = task_id
                result_list.append(result_dict)
                number = get_video_length(settings.NETWORK_STATION + origin_image)
                # print(duration)
                break
            elif status in ["QUEUING", "PROCESSING"]:
                time.sleep(3)
            else:
                result_list.append({"role": "assistant", "url": "", "status": 1, "msg_code": set_flow()})
                break
        return number
