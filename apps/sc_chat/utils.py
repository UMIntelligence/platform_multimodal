#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from _decimal import Decimal

from language.language_pack import RET
from server_chat import settings
from utils import constants
from utils.cst_class import CstException
from utils.request_utils import get_response

timeout = 60
default_model = "default"

unit_price_dict = {         # 单价
        "-2": {default_model: Decimal(0)},          # "识图"
        "0": {default_model: Decimal(43)},          # "gpt35"
        "1": {default_model: Decimal(1312)},       # "gpt40", 成本约0.4376
        "2": {default_model: Decimal(437700)},       # dell 成本约0.1459
        "3": {default_model: Decimal(900000)},    # baidu_drawing   0.3
        "4": {       # "wenxin",
            "completions": Decimal(36),
            "eb-instant": Decimal(24),
            "completions_pro": Decimal(360),
        },
        "5": {      # "xunfei",
            "v1.1": Decimal(54),
            "v2.1": Decimal(108),
            "v3.1": Decimal(108),
        },
        "6": {default_model: Decimal(3000000)},    # "mj", 0.2$
        "7": {default_model: Decimal(36)},    # "claude",
        "8": {           # "CHATGLM",
            "chatglm_turbo": Decimal(15)
        },
        "-3": {           # "CHATGLM",
            "chatglm_turbo": Decimal(15)
        },
        "-4": {           # "CHATGLM",
            "chatglm_turbo": Decimal(0)
        },
        "9": {default_model: Decimal(0)},    # "sd",
        "-1": {default_model: Decimal(0)},    # "sd",
        "10": {     # "qw",
            "qwen-turbo": Decimal(24),
            "qwen-plus": Decimal(60),
        },
        "11": Decimal(36),    # "商汤",
        "12": {           # "360",
            "360GPT_S2_V9": Decimal(36)
        },
        "-5": {           # "360",
            "360GPT_S2_V9": Decimal(0)
        },
        "13": {           # 阿里万相,
            default_model: Decimal(480000)  # 0.16
        },
        "-13": {           # 阿里万相,
            default_model: Decimal(0)  #
        },
        "14": {           # 火山,
            default_model: Decimal(180000)  # 0.06
        },
        "1000": {     # "火山云雀",
            "skylark2-pro-4k": Decimal(45),
            "skylark-pro-public": Decimal(33),
            "skylark-chat": Decimal(33),
            "skylark-plus-public": Decimal(24),
            "skylark-lite-public": Decimal(12),
        },
        "1001": {     # "腾讯混元",
            "ChatStd": Decimal(30),
            "ChatPro": Decimal(300),  # 0.1
        },
        "1002": {     # "讯飞",
            "v2.1": Decimal(90),
        },
        "15": {           # dell3,
            "dall-e-3-0.04": Decimal(875100),  #
            "dall-e-3-0.08": Decimal(1000000),  # 0.5834
            "dall-e-3-0.12": Decimal(1000000),  # 0.8751
        },
        "2000": {default_model: Decimal(1000000)},     # 火山绘画

        "16": {default_model: Decimal(84000)},      # 0.028# 人像年龄变化
        "17": {default_model: Decimal(150000)},     # 0.05 # 智能变美
        "18": {default_model: Decimal(300000)},     # 0.1 # 人像漫画风
        "19": {default_model: Decimal(15000)},     # 0.005 # 文字识别
        "20": {default_model: Decimal(120000)},     # 0.04 # 人像抠图
        "21": {default_model: Decimal(150000)},     # 0.05 # 人像融合
        "22": {default_model: Decimal(600000)},     # 0.2 # 人像特效
        "23": {default_model: Decimal(240000)},     # 0.08 # 发型编辑
        "24": {default_model: Decimal(720000)},     # 0.24 # 3d游戏特效
        "25": {default_model: Decimal(210000)},     # 0.070 # 图片配文
        "26": {default_model: Decimal(240000)},     # 0.08 # 表情编辑
        "27": {default_model: Decimal(60000)},     # 0.02 # 图像增强

        "28": {default_model: Decimal(3000000)},     # 300w # 阿里视频人像卡通
        "29": {default_model: Decimal(1200000)},     # 120w # 通用视频生成
        "30": {default_model: Decimal(2400000)},     # 视频去标志
        "31": {default_model: Decimal(1200000)},     # 120w # 视频去字幕
        "32": {default_model: Decimal(60000)},     # 6w # 照片修图
        "33": {default_model: Decimal(60000)},     # 6w # 图片裁剪
        "34": {default_model: Decimal(300000)},     # 30w # 图像微动
        "35": {default_model: Decimal(600000)},     # 30w # 皮肤检测
        "36": {default_model: Decimal(900000)},     # 90w # 视频降噪
        "37": {default_model: Decimal(1500000)},     # 视频增强
        "38": {default_model: Decimal(120000)},     # 视频封面
        "39": {default_model: Decimal(900000)},     # 面部修复
        "40": {default_model: Decimal(120000)},     # 人脸素描
        "41": {default_model: Decimal(180000)},     # 智能瘦脸
        "42": {default_model: Decimal(300000)},     # 智能美妆
        "43": {default_model: Decimal(450000)},     # 人脸滤镜
        "44": {default_model: Decimal(10000)},     # 人脸模糊
        "45": {default_model: Decimal(10000)},     # 图片字幕擦除
        "46": {default_model: Decimal(240000)},     # 视频评分
        "47": {default_model: Decimal(10000)},     # 物体识别
        "48": {default_model: Decimal(10000)},     # 人脸信息识别
        "49": {default_model: Decimal(30000)},     # 图片标志擦除
        "50": {default_model: Decimal(10000)},     # 商品分割
        "51": {default_model: Decimal(10000)},     # 人体轮廓分割
        "52": {default_model: Decimal(10000)},     # 明星识别

        "53": {default_model: Decimal(10000)},     # 车型识别
        "54": {default_model: Decimal(10000)},     # 图像多主体检测
        "55": {default_model: Decimal(30000)},     # 黑白图像上色
        "56": {default_model: Decimal(135000)},     # 图像风格转换
        "57": {default_model: Decimal(24000)},     # 图像清晰度增强
        "58": {default_model: Decimal(1000000)},     # 智能医学问答

        "60": {default_model: Decimal(0)},     # 视频人脸融合

        "1000010001": {default_model: Decimal(630)},        # tts 普通
        "1000010002": {default_model: Decimal(1260)},        # tts 高级
        "1000010003": {default_model: Decimal(600)},        # tts 百度
        "1000010004": {default_model: Decimal(900)},        # tts 讯飞
        "1000010005": {default_model: Decimal(660)},        # tts 阿里
        "1000010006": {default_model: Decimal(1600)},        # tts 火山
    }


def get_dell_model(data):
    if data["chat_type"] in ["15"]:
        size = data.get("size") or "1024x1024"
        quality = data.get("quality") or "standard"
        str_type = quality + "_" + size
        dict_model = {
            "standard_1024x1024": "dall-e-3-0.04",
            "standard_1024x1792": "dall-e-3-0.08",
            "standard_1792x1024": "dall-e-3-0.08",
            "hd_1024x1024": "dall-e-3-0.08",
            "hd_1024x1792": "dall-e-3-0.12",
            "hd_1792x1024": "dall-e-3-0.12",
        }
        model_name = dict_model[str_type]
    else:
        model_name = default_model
    return model_name


def deduction_calculation(chat_type, tokens, model_name=default_model):
    """
    要扣多少
    :param chat_type:
    :param tokens: 总token数
    :param model_name: 模型
    :return:
    """
    multiple = 10000
    try:
        unit_price = unit_price_dict[chat_type][model_name]     # 单价 1token=多少算力
    except KeyError as e:
        raise CstException(RET.KEY_ERR, "模型异常")
    total_computing_power = unit_price * Decimal(tokens)  # 总算力

    quotient = total_computing_power // multiple  # 计算商
    remainder = total_computing_power % multiple  # 计算余数

    computing_power = quotient * multiple
    if remainder > 0:       # 不足1w算力向上取整
        computing_power += multiple

    # -------------------------5.0前
    # unit_price = unit_price_dict[chat_type]  # 单价 1token=多少算力
    # integral = unit_price * Decimal(tokens)  # 总算力
    # unit_integral = Decimal(str(int(integral)))
    # if unit_integral == 0:
    #     integral = 1
    # else:
    #     quotient = integral // unit_integral  # 计算商
    #     remainder = integral % unit_integral  # 计算余数
    #     integral = quotient * unit_integral
    #     if remainder > 0:  # 不足1算力向上取整
    #         integral += 1
    # print(tokens, integral)
    return int(Decimal(computing_power) / Decimal(10000))


def check_members(user_code, scene=constants.CHAT_SCENE, num=1, bus_type="", status=200, **kwargs):
    """
    会员判断
    """

    members_url = settings.SERVER_COST_URL + f"api/v1/hashrate/{user_code}"
    rsp_data = get_response(members_url, method="get", status=status)
    if not rsp_data:
        raise CstException(RET.NO_ITEM_ERROR, status=status)
    hash_rates = rsp_data["hash_rates"]
    if scene == constants.CHAT_SCENE:
        directed = hash_rates["directed"]
        package = hash_rates["package"]
        if directed <= 0 and package <= 0:
            raise CstException(RET.NO_ITEM_ERROR, status=status)
    elif scene == constants.IMAGE_SCENE:   # 绘画
        req_data = kwargs.get("data") or {}
        model_name = get_dell_model(req_data)
        chat_type = req_data.get("chat_type")
        n = str(req_data.get("n") or num)
        unit_price = deduction_calculation(chat_type, n, model_name)
        member_total = hash_rates["member_total"]
        package = hash_rates["package"]

        if member_total + package < unit_price:
            raise CstException(RET.NO_ITEM_ERROR, status=status)
    else:
        unit_price = deduction_calculation(bus_type, num)
        member_total = hash_rates["member_total"]
        package = hash_rates["package"]

        if member_total + package < unit_price:
            raise CstException(RET.NO_ITEM_ERROR, status=status)
    return rsp_data


def charges_api(user_code, computing_power, scene=1):
    """
    扣费
    :param user_code:
    :param computing_power:
    :param scene: 场景标识，1对话，2其他
    :return:
    """
    if scene == 1:
        status = 400
    else:
        status = 200
    url = settings.SERVER_COST_URL + """api/v1/hashrate"""
    send_data = {
        "user_id": user_code,
        "hashrate": computing_power,
        "scene": scene
    }
    print(send_data)
    data = get_response(url, send_data, timeout=timeout, method="put", status=status)
    return data
