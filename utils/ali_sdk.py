#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import base64
import io
import json
import random
import re
import uuid
from http import HTTPStatus
from typing import BinaryIO
from urllib.request import urlopen

import dashscope
import requests
from alibabacloud_tea_util.models import RuntimeOptions
from alibabacloud_viapi20230117.models import GetAsyncJobResultRequest
from alibabacloud_videoenhan20200320.client import Client as video_client
from alibabacloud_videorecog20200320.client import Client as video_cog_client
from alibabacloud_facebody20191230.client import Client as face_body_client
from alibabacloud_objectdet20191230.client import Client as object_det_client
from alibabacloud_imageseg20191230.client import Client as image_seg_client
from alibabacloud_green20220302 import models as green_20220302_models
from alibabacloud_imageseg20191230 import models as image_seg_models
from alibabacloud_facebody20191230 import models as face_body_20191230_models
from alibabacloud_green20220302.client import Client as Green20220302Client
from alibabacloud_imageenhan20190930 import models as imageenhan_20190930_models
from alibabacloud_objectdet20191230 import models as object_det_models
from alibabacloud_imageenhan20190930.client import Client as imageenhan20190930Client
from alibabacloud_imageprocess20200320 import models as imageprocess_20200320_models
from alibabacloud_imageprocess20200320.client import Client as imageprocess20200320Client
from alibabacloud_ocr_api20210707 import models as ocr_api_20210707_models
from alibabacloud_ocr_api20210707.client import Client as ocr_api20210707Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_tea_util import models as util_models
from alibabacloud_tea_util.client import Client as UtilClient
from alibabacloud_videoenhan20200320.models import GenerateHumanAnimeStyleVideoAdvanceRequest, \
    GenerateVideoAdvanceRequest, GenerateVideoAdvanceRequestFileList, EraseVideoLogoAdvanceRequest, \
    EraseVideoSubtitlesAdvanceRequest, ReduceVideoNoiseAdvanceRequest, EnhanceVideoQualityAdvanceRequest
from alibabacloud_videorecog20200320 import models as video_model
from aliyunsdkcore.client import AcsClient
from aliyunsdkcore.http import method_type
from aliyunsdkcore.request import CommonRequest
from dashscope import ImageSynthesis
from dashscope.common.constants import TaskStatus
from django_redis import get_redis_connection
from viapi.fileutils import FileUtils

import nls
from language.language_pack import RET
from server_chat import settings
from utils.cst_class import CstException
from utils.sso_utils import ToOss

resp_msg_list = [
    "您所问的问题涉及敏感字眼，请重新提问。",
    "很抱歉，作为一名AI助手，我不能提供任何违反相关法律法规和道德规范的建议或支持。",
    "作为人工智能助手，我会遵守相关法律法规和道德准则，避免回答任何涉及敏感字眼的问题。请您理解和配合。",
    "作为一名AI助手，我会遵守相关法律法规和道德规范，避免回答任何敏感、不当的问题或内容。请提出其他问题，我将尽力为您提供有用的答案和支持。",
    "很抱歉，作为人工智能语言模型，我不会使用或提供含有敏感字眼的答复。我将始终遵守所有适用的法律和规定，并确保我的回复尊重和保护人权和隐私。",
    "如果您提出了一些敏感问题或包含敏感字眼的问题，我很抱歉我不能回答。 作为AI语言模型，我受到道德和法律标准的约束，不能够提供任何可能引起任何形式的负面影响或违反法律或伦理规定的建议或答复。 请提出其他问题，我将尽力为您提供有用的答案和支持。",
]


class Sample:
    def __init__(self):
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=settings.ALI_APP_ID,
            # 必填，您的 AccessKey Secret,
            access_key_secret=settings.ALI_APP_SECRET
        )
        # 访问的域名
        config.endpoint = f'green-cip.cn-shanghai.aliyuncs.com'
        self.client = Green20220302Client(config)

    def ali_text_mod(self, parameters, service="chat_detection", status=200) -> None:
        text_moderation_request = green_20220302_models.TextModerationRequest(
            service=service,
            service_parameters=parameters
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            resp = self.client.text_moderation_with_options(text_moderation_request, runtime).body
        except Exception as error:
            # 如有需要，请打印 error
            # UtilClient.assert_as_string(error.message)\
            raise CstException(RET.REASON_ERR, error, status=status)
        if resp.code != 200:
            raise CstException(RET.REASON_ERR, f"敏感词检测异常：{resp.message}", status=status)

        if resp.data.reason:
            raise CstException(RET.REASON_ERR, random.choice(resp_msg_list), status=status)

        return resp.data

    def ali_image_mod(self, image_url, service="baselineCheck", status=200):
        service_parameters = {
            'imageUrl': image_url,
            'dataId': str(uuid.uuid1())
        }
        image_moderation_request = green_20220302_models.ImageModerationRequest(
            # 检测类型: baselineCheck 通用基线检测。
            service=service,
            service_parameters=json.dumps(service_parameters)
        )
        runtime = util_models.RuntimeOptions()
        runtime.read_timeout = 10000
        runtime.connect_timeout = 10000

        try:
            response = self.client.image_moderation_with_options(image_moderation_request, runtime)
        except Exception as e:
            raise CstException(RET.REASON_ERR, str(e), status=status)
        if response.status_code == 200:
            # 调用成功。
            # 获取审核结果。
            result = response.body
            if result.code != 200:
                raise CstException(RET.REASON_ERR, f"敏感图片检测异常：{result}", status=status)
            else:
                result_data = result.data
                result = result_data.result or []
                for i in result:
                    if i.label == 'nonLabel':
                        pass
                    else:
                        print(i)
                        if i.confidence >= 88:
                            raise CstException(RET.REASON_ERR, f"图片违规：违规标签：{i.confidence}", status=status)
                return result_data
        else:
            raise CstException(RET.REASON_ERR, f"敏感图片检测异常", status=status)


ali_client = Sample()


class OcrSample:
    def __init__(self):
        pass

    @staticmethod
    def create_client(
            access_key_id=settings.ALI_APP_ID,
            access_key_secret=settings.ALI_APP_SECRET,
    ) -> ocr_api20210707Client:
        """
        使用AK&SK初始化账号Client
        @param access_key_id:
        @param access_key_secret:
        @return: Client
        @throws Exception
        """
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=access_key_id,
            # 必填，您的 AccessKey Secret,
            access_key_secret=access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/ocr-api
        config.endpoint = f'ocr-api.cn-hangzhou.aliyuncs.com'
        return ocr_api20210707Client(config)

    @staticmethod
    def recognize_general(url: str = None, body: BinaryIO = None) -> None:
        client = OcrSample.create_client()
        recognize_general_request = ocr_api_20210707_models.RecognizeGeneralRequest(url=url, body=body)
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            result = client.recognize_general_with_options(recognize_general_request, runtime)
            return json.loads(result.body.data)
        except Exception as error:
            UtilClient.assert_as_string(error.message)
            raise CstException(RET.DATE_ERROR, f"图片检测失败，原因：{error.message}")

    @staticmethod
    async def recognize_general_async(url: str = None, body: BinaryIO = None) -> None:
        client = OcrSample.create_client()
        recognize_general_request = ocr_api_20210707_models.RecognizeGeneralRequest(url=url, body=body)
        runtime = util_models.RuntimeOptions()
        try:
            result = await client.recognize_general_with_options_async(recognize_general_request, runtime)
            return json.loads(result.body.data)
        except Exception as error:
            # 如有需要，请打印 error
            UtilClient.assert_as_string(error.message)
            raise CstException(RET.DATE_ERROR, f"图片检测失败，原因：{error.message}")


ocr_recognize = OcrSample()


class AliVideoCapacitySdk(object):
    def __init__(self):
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=settings.ALI_APP_ID,
            # 必填，您的 AccessKey Secret,
            access_key_secret=settings.ALI_APP_SECRET,
            endpoint='videoenhan.cn-shanghai.aliyuncs.com',
            # 访问的域名对应的region
            region_id='cn-shanghai'
        )
        self.client = video_client(config)

    def generate_anime_video(self, video_url, style):
        img = io.BytesIO(urlopen(video_url).read())
        generate_human_anime_style_video_request = GenerateHumanAnimeStyleVideoAdvanceRequest(
            video_url_object=img,
            cartoon_style=style
        )
        runtime = RuntimeOptions()
        try:
            response = self.client.generate_human_anime_style_video_advance(
                generate_human_anime_style_video_request, runtime)
            # 获取整体结果
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def get_async_job_result(self, task_id):
        """
        结果查询
        :param task_id:
        :return:
        """
        get_async_job_result_request = GetAsyncJobResultRequest(
            job_id=task_id
        )
        runtime = RuntimeOptions()
        try:
            response = self.client.get_async_job_result_with_options(get_async_job_result_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR)
        return response.body

    def generate_video_create(self, file_list, width, height, style, transition_style, scene):
        send_file_list = []

        for i in file_list:
            g_list = GenerateVideoAdvanceRequestFileList()
            file_url = settings.NETWORK_STATION + i["file_url"]
            g_list.file_url_object = io.BytesIO(urlopen(file_url).read())
            g_list.type = i["file_type"]
            g_list.file_name = i["file_name"]
            send_file_list.append(g_list)

        generate_video_request = GenerateVideoAdvanceRequest(
            scene=scene,
            width=width,
            height=height,
            style=style,
            duration=20,
            duration_adaption=True,
            transition_style=transition_style,
            file_list=send_file_list,
        )
        runtime_option = RuntimeOptions()
        try:
            response = self.client.generate_video_advance(generate_video_request, runtime_option)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def erase_video_logo(self, video_url):
        img = io.BytesIO(urlopen(video_url).read())
        erase_video_logo_request = EraseVideoLogoAdvanceRequest(
            video_url_object=img
        )
        runtime_option = RuntimeOptions()
        try:
            response = self.client.erase_video_logo_advance(erase_video_logo_request, runtime_option)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def erase_video_subtitles(self, video_url):
        img = io.BytesIO(urlopen(video_url).read())
        erase_video_subtitles_request = EraseVideoSubtitlesAdvanceRequest(
            video_url_object=img
        )
        runtime_option = RuntimeOptions()
        try:
            response = self.client.erase_video_subtitles_advance(erase_video_subtitles_request, runtime_option)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def reduce_video_noise(self, video_url):
        video = io.BytesIO(urlopen(video_url).read())
        reduce_video_noise_request = ReduceVideoNoiseAdvanceRequest(video)
        runtime = RuntimeOptions()
        try:
            response = self.client.reduce_video_noise_advance(reduce_video_noise_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def enhance_video_quality(self, video_url):
        video = io.BytesIO(urlopen(video_url).read())
        enhance_video_quality_request = EnhanceVideoQualityAdvanceRequest(
            video_urlobject=video,
        )
        runtime = RuntimeOptions()
        try:
            response = self.client.enhance_video_quality_advance(enhance_video_quality_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body


ali_video_obj = AliVideoCapacitySdk()


class AliVideoVideoCogSdk(object):
    def __init__(self):
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=settings.ALI_APP_ID,
            # 必填，您的 AccessKey Secret,
            access_key_secret=settings.ALI_APP_SECRET,
            endpoint='videorecog.cn-shanghai.aliyuncs.com',
            # 访问的域名对应的region
            region_id='cn-shanghai'
        )
        self.client = video_cog_client(config)

    def generate_video_cover(self, video_url, is_gif):
        video = io.BytesIO(urlopen(video_url).read())
        generate_video_cover_request = video_model.GenerateVideoCoverAdvanceRequest(
            is_gif=is_gif,
            video_url_object=video
        )
        runtime = RuntimeOptions()
        try:
            response = self.client.generate_video_cover_advance(generate_video_cover_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def evaluate_video_quality(self, video_url, mode):
        video = io.BytesIO(urlopen(video_url).read())
        evaluate_video_quality_request = video_model.EvaluateVideoQualityAdvanceRequest(
            mode=mode,
            video_url_object=video
        )
        runtime = RuntimeOptions()
        try:
            response = self.client.evaluate_video_quality_advance(evaluate_video_quality_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body


ali_video_cog_obj = AliVideoVideoCogSdk()


class AliFaceBodySdk(object):
    def __init__(self):
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=settings.ALI_APP_ID,
            # 必填，您的 AccessKey Secret,
            access_key_secret=settings.ALI_APP_SECRET,
            endpoint='facebody.cn-shanghai.aliyuncs.com',
            # 访问的域名对应的region
            region_id='cn-shanghai'
        )
        self.client = face_body_client(config)

    def enhance_face_options(self, image_url):
        image = io.BytesIO(urlopen(image_url).read())
        enhance_face_request = face_body_20191230_models.EnhanceFaceAdvanceRequest(
            image_urlobject=image
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.enhance_face_advance(enhance_face_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def generate_human_sketch_style(self, image_url, return_type):
        image = io.BytesIO(urlopen(image_url).read())
        generate_human_sketch_style_request = face_body_20191230_models.GenerateHumanSketchStyleAdvanceRequest(
            return_type=return_type,
            image_urlobject=image
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.generate_human_sketch_style_advance(generate_human_sketch_style_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def liquify_face(self, image_url, slim_degree):
        image = io.BytesIO(urlopen(image_url).read())
        liquify_face_request = face_body_20191230_models.LiquifyFaceAdvanceRequest(
            slim_degree=float(slim_degree),
            image_urlobject=image
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.liquify_face_advance(liquify_face_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def face_makeup(self, image_url, resource_type, strength):
        image = io.BytesIO(urlopen(image_url).read())
        face_makeup_request = face_body_20191230_models.FaceMakeupAdvanceRequest(
            makeup_type="whole",
            image_urlobject=image,
            resource_type=resource_type,
            strength=strength
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.face_makeup_advance(face_makeup_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def face_filter(self, image_url, resource_type, strength):
        image = io.BytesIO(urlopen(image_url).read())
        face_filter_request = face_body_20191230_models.FaceFilterAdvanceRequest(
            image_urlobject=image,
            resource_type=resource_type,
            strength=strength
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.face_filter_advance(face_filter_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def blur_face(self, image_url):
        image = io.BytesIO(urlopen(image_url).read())
        blur_face_request = face_body_20191230_models.BlurFaceAdvanceRequest(
            image_urlobject=image
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.blur_face_advance(blur_face_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def recognize_face(self, image_url):
        image = io.BytesIO(urlopen(image_url).read())
        recognize_face_request = face_body_20191230_models.RecognizeFaceAdvanceRequest(
            image_urlobject=image
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.recognize_face_advance(recognize_face_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def detect_celebrity(self, image_url):
        image = io.BytesIO(urlopen(image_url).read())
        detect_celebrity_request = face_body_20191230_models.DetectCelebrityAdvanceRequest(
            image_urlobject=image
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.detect_celebrity_advance(detect_celebrity_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body


ali_face_body_obj = AliFaceBodySdk()


class AliObjectDetSdk(object):
    def __init__(self):
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=settings.ALI_APP_ID,
            # 必填，您的 AccessKey Secret,
            access_key_secret=settings.ALI_APP_SECRET,
            endpoint='objectdet.cn-shanghai.aliyuncs.com',
            # 访问的域名对应的region
            # region_id='cn-shanghai'
        )
        self.client = object_det_client(config)

    def detect_object(self, image_url):
        image = io.BytesIO(urlopen(image_url).read())
        detect_object_request = object_det_models.DetectObjectAdvanceRequest(
            image_urlobject=image
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.detect_object_advance(detect_object_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body


object_det_obj = AliObjectDetSdk()


class ImageSegSdk(object):
    def __init__(self):
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=settings.ALI_APP_ID,
            # 必填，您的 AccessKey Secret,
            access_key_secret=settings.ALI_APP_SECRET,
            endpoint='imageseg.cn-shanghai.aliyuncs.com',
            # 访问的域名对应的region
            # region_id='cn-shanghai'
        )
        self.client = image_seg_client(config)

    def segment_commodity(self, image_url, return_form):
        image = io.BytesIO(urlopen(image_url).read())
        segment_commodity_request = image_seg_models.SegmentCommodityAdvanceRequest(
            image_urlobject=image,
            return_form=return_form
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.segment_commodity_advance(segment_commodity_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body

    def segment_body(self, image_url, return_form):
        image = io.BytesIO(urlopen(image_url).read())
        segment_body_request = image_seg_models.SegmentBodyAdvanceRequest(
            image_urlobject=image,
            return_form=return_form
        )
        runtime = util_models.RuntimeOptions()
        try:
            response = self.client.segment_body_advance(segment_body_request, runtime)
        except Exception as error:
            raise CstException(RET.THIRD_ERROR, error.message)
        return response.body


image_seg_obj = ImageSegSdk()


class ImageScore(object):
    def __init__(self):
        pass

    @staticmethod
    def create_client(
        access_key_id=settings.ALI_APP_ID,
        access_key_secret=settings.ALI_APP_SECRET,
    ) -> imageenhan20190930Client:
        """
        使用AK&SK初始化账号Client
        @param access_key_id:
        @param access_key_secret:
        @return: Client
        @throws Exception
        """
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=access_key_id,
            # 必填，您的 AccessKey Secret,
            access_key_secret=access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/imageenhan
        config.endpoint = f'imageenhan.cn-shanghai.aliyuncs.com'
        return imageenhan20190930Client(config)

    @staticmethod
    def score_run(url) -> float:
        client = ImageScore.create_client()
        assess_composition_request = imageenhan_20190930_models.AssessCompositionRequest(
            image_url=url
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            result = client.assess_composition_with_options(assess_composition_request, runtime)
            # print(result)
            if result.status_code == 200:
                score = result.body.data.score
                return score
            else:
                raise CstException(RET.DATE_ERROR, f"图片评分失败")
        except Exception as error:
            # 如有需要，请打印 error
            UtilClient.assert_as_string(error.message)
            raise CstException(RET.DATE_ERROR, f"图片评分失败，原因：{error.message}")

    @staticmethod
    async def main_async(url) -> float:
        client = ImageScore.create_client()
        assess_composition_request = imageenhan_20190930_models.AssessCompositionRequest(
            image_url=url
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            result = await client.assess_composition_with_options_async(assess_composition_request, runtime)
            if result.status_code == 200:
                score = result.body.data.score
                return score
            else:
                raise CstException(RET.DATE_ERROR, f"图片评分失败")
        except Exception as error:
            # 如有需要，请打印 error
            UtilClient.assert_as_string(error.message)
            raise CstException(RET.DATE_ERROR, f"图片评分失败，原因：{error.message}")

    def imitate_photo_style(self, image_url, style_url):
        client = self.create_client()
        image_url = get_oss_url(image_url)
        style_url = get_oss_url(style_url)
        imitate_photo_style_request = imageenhan_20190930_models.ImitatePhotoStyleRequest(
            image_url=image_url,
            style_url=style_url,
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = client.imitate_photo_style_with_options(imitate_photo_style_request, runtime)
        except Exception as error:
            raise CstException(RET.DATE_ERROR, error.message)
        if rsp.status_code == 200:
            result_image = rsp.body.data
            return result_image
        else:
            raise CstException(RET.DATE_ERROR, f"图片生成失败")

    def change_image_size(self, width, height, url):
        client = self.create_client()
        url = get_oss_url(url)
        change_image_size_request = imageenhan_20190930_models.ChangeImageSizeRequest(
            width=width,
            height=height,
            url=url,
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = client.change_image_size_with_options(change_image_size_request, runtime)
        except Exception as error:
            raise CstException(RET.DATE_ERROR, error.message)
        if rsp.status_code == 200:
            result_image = rsp.body.data
            return result_image
        else:
            raise CstException(RET.DATE_ERROR, f"图片裁剪失败")

    def generate_dynamic_image(self, url, operation):
        client = self.create_client()
        url = get_oss_url(url)
        generate_dynamic_image_request = imageenhan_20190930_models.GenerateDynamicImageRequest(
            url=url,
            operation=operation
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = client.generate_dynamic_image_with_options(generate_dynamic_image_request, runtime)
        except Exception as error:
            raise CstException(RET.DATE_ERROR, error.message)
        if rsp.status_code == 200:
            result_image = rsp.body.data
            return result_image
        else:
            raise CstException(RET.DATE_ERROR, f"图片微动失败")

    def remove_image_subtitles(self, url):
        client = self.create_client()
        url = get_oss_url(url)
        remove_image_subtitles_request = imageenhan_20190930_models.RemoveImageSubtitlesRequest(
            image_url=url
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = client.remove_image_subtitles_with_options(remove_image_subtitles_request, runtime)
        except Exception as error:
            raise CstException(RET.DATE_ERROR, error.message)
        if rsp.status_code == 200:
            result_image = rsp.body.data
            return result_image
        else:
            raise CstException(RET.DATE_ERROR, f"字幕擦除失败")

    def remove_image_watermark(self, url):
        client = self.create_client()
        url = get_oss_url(url)
        remove_image_watermark_request = imageenhan_20190930_models.RemoveImageWatermarkRequest(
            image_url=url
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = client.remove_image_watermark_with_options(remove_image_watermark_request, runtime)
        except Exception as error:
            raise CstException(RET.DATE_ERROR, error.message)
        if rsp.status_code == 200:
            result_image = rsp.body.data
            return result_image
        else:
            raise CstException(RET.DATE_ERROR, f"标志擦除失败")


ali_image_obj = ImageScore()


def url_to_base64(url):
    try:
        response = requests.get(url)
    except Exception as e:
        raise CstException("网络异常，图片访问失败!")
    image_content = response.content
    base64_string = base64.b64encode(image_content)
    return base64_string.decode('utf-8')


class ImageAnalysis(object):
    """图像分析"""

    def __init__(self, access_key_id=settings.ALI_APP_ID, access_key_secret=settings.ALI_APP_SECRET):
        """
        使用AK&SK初始化账号Client
        @param access_key_id:
        @param access_key_secret:
        """
        config = open_api_models.Config(
            # 必填，您的 AccessKey ID,
            access_key_id=access_key_id,
            # 必填，您的 AccessKey Secret,
            access_key_secret=access_key_secret
        )
        # Endpoint 请参考 https://api.aliyun.com/product/imageenhan
        config.endpoint = f'imageprocess.cn-shanghai.aliyuncs.com'
        self.client = imageprocess20200320Client(config)

    def detect_skin_disease(self, url):
        url = get_oss_url(url)
        detect_skin_disease_request = imageprocess_20200320_models.DetectSkinDiseaseRequest(
            url=url,
            org_id='0001',
            org_name='demo'
        )
        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = self.client.detect_skin_disease_with_options(detect_skin_disease_request, runtime)
        except Exception as error:
            raise CstException(RET.DATE_ERROR, error.message)
        if rsp.status_code == 200:
            result_image = rsp.body.data
            return result_image
        else:
            raise CstException(RET.DATE_ERROR, f"皮肤检测失败")

    def run_med(self, question_type, session_id, file_list, prompt):
        answer_image_data_list = []
        answer_text_list_0 = imageprocess_20200320_models.RunMedQARequestAnswerTextList(
            answer_text=prompt
        )
        for f in file_list:
            image_url = settings.NETWORK_STATION + f
            image = url_to_base64(image_url)
            image_data = imageprocess_20200320_models.RunMedQARequestAnswerImageDataList(
                answer_image_data=image
            )
            answer_image_data_list.append(image_data)

        run_med_qarequest = imageprocess_20200320_models.RunMedQARequest(
            org_id='0001',
            org_name='weiyi',
            department='皮肤科',
            question_type=question_type,
            answer_image_data_list=answer_image_data_list,
            answer_text_list=[answer_text_list_0],
            session_id=session_id
        )

        runtime = util_models.RuntimeOptions()
        try:
            # 复制代码运行请自行打印 API 的返回值
            rsp = self.client.run_med_qawith_options(run_med_qarequest, runtime)
        except Exception as error:
            raise CstException(RET.DATE_ERROR, error.message)
        if rsp.status_code == 200:
            result_image = rsp.body.data
            return result_image
        else:
            raise CstException(RET.DATE_ERROR, f"提问失败")


ali_image_analysis = ImageAnalysis()


class RecordingFileRecognition(object):
    # 文档地址https://help.aliyun.com/document_detail/90727.html?spm=a2c4g.90726.0.0.4e1a4938DdPbI8
    API_VERSION = "2018-08-17"
    PRODUCT = "nls-filetrans"
    GET_REQUEST_ACTION = "GetTaskResult"

    def __init__(self, ak=settings.ALI_APP_ID, sk=settings.ALI_APP_SECRET):
        self.client = AcsClient(ak, sk, "cn-shenzhen")
        self.url = "filetrans.cn-shanghai.aliyuncs.com"

    def get_send_request(self, task_id):
        req = CommonRequest()
        req.set_domain(self.url)
        req.set_version(self.API_VERSION)
        req.set_product(self.PRODUCT)
        req.set_action_name(self.GET_REQUEST_ACTION)
        req.set_method('GET')
        req.add_query_param("TaskId", task_id)
        # 提交录音文件识别结果查询请求
        # 以轮询的方式进行识别结果的查询，直到服务端返回的状态描述符为"SUCCESS"、"SUCCESS_WITH_NO_VALID_FRAGMENT"，
        # 或者为错误描述，则结束轮询。
        try:
            resp = self.client.do_action_with_exception(req)
            resp = json.loads(resp)
        except Exception as e:
            raise CstException(RET.DATE_ERROR, "请求失败")
        # if resp.get("StatusCode") != 21050000:
        #     raise CstException(RET.DATE_ERROR, )
        return resp

    def post_send_request(self, file_link):
        # 提交录音文件识别请求

        post_request = CommonRequest()
        post_request.set_domain(self.url)
        post_request.set_version(self.API_VERSION)
        post_request.set_product(self.PRODUCT)
        post_request.set_action_name("SubmitTask")
        post_request.set_method('POST')
        # 开启智能分轨，如果开启智能分轨，task中设置KEY_AUTO_SPLIT为True。
        task = {
            "appkey": settings.A_APP_KEY,
            "file_link": file_link,
            "version": "4.0",
            "enable_words": False,
            "auto_split": True,
            "enable_sample_rate_adaptive": True,
            "first_channel_only": True,
            "speaker_num": True,
            # "enable_callback": True,
            # "callback_url": settings.CALLBACK + "api/sv_voice/file_identifier_call"
        }
        task = json.dumps(task)
        # print(task)
        post_request.add_body_params("Task", task)
        return post_request

    def send_request(self, file_link):
        post_request = self.post_send_request(file_link)
        try:
            resp = self.client.do_action_with_exception(post_request)
            resp = json.loads(resp)
        except Exception as e:
            raise CstException(RET.DATE_ERROR, "发送文件失败")
        status_text = resp["StatusText"]
        if status_text == "SUCCESS":
            task_id = resp["TaskId"]
        else:
            raise CstException(RET.DATE_ERROR, "录音文件识别请求失败！")
        return task_id


def get_suffix(url, suffix="png"):
    match = re.search(r'\.([^.]*?)(?:\?|$)', url)
    if match:
        suffix = match.group(1)
    else:
        suffix = suffix
    return suffix


def get_oss_url(url, suffix="png"):
    suffix = get_suffix(url, suffix)

    file_utils = FileUtils(settings.ACCESS_KEY_ID, settings.ACCESS_KEY_SECRET)
    # 场景一，使用本地文件，第一个参数为文件路径，第二个参数为生成的url后缀，但是并不能通过这种方式改变真实的文件类型，第三个参数True表示本地文件模式
    # oss_url = file_utils.get_oss_url("/tmp/bankCard.png", "png", True)
    # 场景二，使用任意可访问的url，第一个url，第二个参数为生成的url后缀，但是并不能通过这种方式改变真实的文件类型，第三个参数False表示非本地文件模式
    oss_url = file_utils.get_oss_url(url, suffix, False)
    # 生成的url，可用于调用视觉智能开放平台的能力
    # print(oss_url)
    return oss_url


class SoundCloneSdk(object):
    """声音克隆"""
    # 文档地址https://help.aliyun.com/document_detail/456007.html?spm=a2c4g.374323.0.0.d2704d26pBt0o7#cfd05d908029x
    API_VERSION = "2019-09-05"
    PRODUCT = "nls-filetrans"
    GET_REQUEST_ACTION = "GetTaskResult"
    domain = 'nls-measure.cn-shanghai.aliyuncs.com'
    # voice训练基础信息
    scenario = 'story'
    gender = 'female'

    def __init__(self, ak=settings.ALI_APP_ID, sk=settings.ALI_APP_SECRET):
        self.client = AcsClient(ak, sk, "cn-shanghai")

    def build_request(self, api_name):
        request = CommonRequest()
        request.set_domain(self.domain)
        request.set_version(self.API_VERSION)
        request.set_action_name(api_name)
        request.set_method(method_type.POST)
        return request

    def get_for_customized_voice(self):
        # step1: 获取需要朗读的文本
        get_demonstration_request = self.build_request('GetDemonstrationForCustomizedVoice')
        get_demonstration_request.add_query_param('Scenario', self.scenario)
        try:
            get_demonstration_response = self.client.do_action_with_exception(get_demonstration_request)
            resp = json.loads(get_demonstration_response)
        except Exception as e:
            raise CstException(RET.DATE_ERROR, "请求失败")
        # if not resp.get("Success"):
        #     raise CstException(RET.DATE_ERROR, "请求失败")
        return resp.get("Data")

    def customized_voice_audio_detect(self, voice_name, voice_list, redis_conn):
        for voice in voice_list:
            record_url = voice.get("audio_record_url")
            audio_record_url = settings.NETWORK_STATION + record_url
            audio_record_id = voice.get("audio_record_id")
            audio_detect_request = self.build_request('CustomizedVoiceAudioDetect')
            audio_detect_request.add_query_param('Scenario', self.scenario)
            audio_detect_request.add_query_param('VoiceName', voice_name)
            audio_detect_request.add_query_param('RecordUrl', audio_record_url)
            audio_detect_request.add_query_param('AudioRecordId', audio_record_id)
            try:
                get_demonstration_response = self.client.do_action_with_exception(audio_detect_request)
                resp = json.loads(get_demonstration_response)
            except Exception as e:
                raise CstException(RET.DATE_ERROR, f"第{audio_record_id}个视频检测失败")
            if not resp.get("Success"):
                raise CstException(RET.DATE_ERROR, f"请求声音检测失败,原因:{resp.get('ErrorMessage')}")
            data = resp.get("Data")
            if not data.get("pass"):
                raise CstException(RET.DATE_ERROR, f"第{audio_record_id}个视频检测失败,失败原因：{data.get('reason')}")
            h_dict = {"audio_record_url": record_url, "audio_record_id": audio_record_id}
            if not redis_conn.exists(voice_name):
                s = json.dumps([h_dict])
                redis_conn.set(voice_name, s)
            else:
                voice_info = redis_conn.get(voice_name)
                voice_info = json.loads(voice_info)
                r_id_list = [i.get("audio_record_id") for i in voice_info]
                if audio_record_id not in r_id_list:
                    voice_info.append(h_dict)
                else:
                    r_index = r_id_list.index(audio_record_id)
                    voice_info[r_index]["audio_record_url"] = record_url
                s = json.dumps(voice_info)
                redis_conn.set(voice_name, s)

    def submit_voice(self, voice_name, gender):
        # step3: 提交训练
        submit_train_request = self.build_request('SubmitCustomizedVoice')
        submit_train_request.add_query_param('Scenario', self.scenario)
        submit_train_request.add_query_param('VoiceName', voice_name)
        submit_train_request.add_query_param('Gender', gender)      # female：女性 male：男性
        try:
            submit_train_response = self.client.do_action_with_exception(submit_train_request)
            resp = json.loads(submit_train_response)
        except Exception as e:
            raise CstException(RET.DATE_ERROR, "提交失败")
        if not resp.get("Success"):
            raise CstException(RET.DATE_ERROR, f"提交训练失败, 原因：{resp.get('ErrorMessage')}")
        return resp

    def list_customized_voice(self, voice_name):
        # step4: 查询训练结果
        query_train_result_request = self.build_request('ListCustomizedVoice')
        query_train_result_request.add_query_param('VoiceName', voice_name)

        try:
            query_train_result_response = self.client.do_action_with_exception(query_train_result_request)
            resp = json.loads(query_train_result_response)
        except Exception as e:
            raise CstException(RET.DATE_ERROR, "查询失败")
        data = resp.get("Data")
        if data:
            data = data[0]
        return data


class VoiceTts:
    # URL = "wss://nls-gateway.cn-shanghai.aliyuncs.com/ws/v1"
    URL = "wss://nls-gateway-cn-shenzhen.aliyuncs.com/ws/v1"
    APP_KEY = settings.A_APP_KEY

    def __init__(self, token, long_tts=False):
        self.token = token
        self.oss_obj = ToOss()
        self.tts = nls.NlsSpeechSynthesizer(url=self.URL, token=self.token, appkey=self.APP_KEY,
                                            long_tts=long_tts,
                                            on_metainfo=self.on_metainfo,
                                            on_data=self.on_data,
                                            on_completed=self.on_completed,
                                            on_error=self.on_error,
                                            on_close=self.on_close)

    def start(self, text, voice, volume, speech_rate, pitch_rate, enable_ptts=True, oss_dir="digital_human"):
        self.__text = text
        self.__voice = voice
        self.__f = io.BytesIO()
        # self.__f = open("1.wav", "wb")
        return self.__test_run(volume, speech_rate, pitch_rate, enable_ptts, oss_dir)

    def on_metainfo(self, message, *args):
        print("on_metainfo message=>{}".format(message))

    def on_error(self, message, *args):
        print("on_error args=>{}".format(args))

    def on_close(self, *args):
        print("on_close: args=>{}".format(args))
        try:
            # self.__f.close()
            self.tts.shutdown()
        except Exception as e:
            print("close file failed since:", e)

    def on_data(self, data, *args):
        try:
            # print(data)
            self.__f.write(data)
        except Exception as e:
            print("write data failed:", e)

    def on_completed(self, message, *args):
        print("on_completed:args=>{} message=>{}".format(args, message))

    def __test_run(self, volume, speech_rate, pitch_rate, enable_ptts, oss_dir):
        ex = {"enable_ptts": enable_ptts}
        r = self.tts.start(self.__text, voice=self.__voice, aformat="wav",
                           volume=volume, speech_rate=speech_rate, pitch_rate=pitch_rate, completed_timeout=500,
                           ex=ex)
        oss_url = self.oss_obj.main("voice", oss_dir=oss_dir, file_con=self.__f.getvalue(), file_extension="wav")
        self.__f.close()
        return oss_url


def simple_image_call(send_data):
    """同步"""
    redis_conn = get_redis_connection('config')
    api_key = redis_conn.get("TYQW_APP_ID")
    dashscope.api_key = api_key
    rsp = ImageSynthesis.call(model=ImageSynthesis.Models.wanx_v1,
                              prompt=send_data.get("prompt"),
                              negative_prompt=send_data.get("negative_prompt") or None,
                              images=send_data.get("images") or None,
                              n=send_data.get("n") or 1,
                              style=send_data.get("style"),
                              size=send_data.get("size"))
    if rsp.status_code == HTTPStatus.OK:
        if rsp.output is None:
            raise CstException(RET.DATE_ERROR, "生成失败，请重试")
        task_status = rsp.output['task_status']
        if task_status in TaskStatus.CANCELED:
            raise CstException(RET.DATE_ERROR, "任务已被取消")
        if task_status in TaskStatus.FAILED:
            raise CstException(RET.DATE_ERROR, rsp.output.message)
        return rsp
    else:
        raise CstException(RET.DATE_ERROR, rsp.message)


# 取消异步任务，只有处于PENDING状态的任务才可以取消
def cancel_task(task):
    rsp = ImageSynthesis.cancel(task)
    print(rsp)
    if rsp.status_code == HTTPStatus.OK:
        print(rsp.output.task_status)
    else:
        print('Failed, status_code: %s, code: %s, message: %s' %
              (rsp.status_code, rsp.code, rsp.message))