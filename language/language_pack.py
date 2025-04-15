#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


class RET:
    """
    语言类包
    """
    OK = 20000
    FREQUENTLY = 40009
    DATE_ERROR = 40017
    THIRD_ERROR = 40027
    INTEGRAL_ERROR = 40028
    MAX_RETRY_ERROR = 40029
    NO_DATE_ERROR = 40018
    LACK_ERROR = 40020
    LACK_MAX_ERROR = 40021
    NO_ITEM_ERROR = 40022
    NOT_FOUND = 40004
    SERVER_ERROR = 50000
    DB_ERR = 50001
    TP_ERR = 40023
    MAX_TOKENS_ERR = 40100
    AUTH_ERR = 40013
    USER_ERR = 40012
    NO_VIP = 30014
    REASON_ERR = 40015
    MAX_C_ERR = 40024
    MODEL_ERR = 40025
    KEY_ERR = 40016
    NO_NUMBER = 40040


# 元组中第一个为中文，第二个为英文，第三个为繁体
language_pack = {
    RET.OK: ("成功",),
    RET.FREQUENTLY: ("使用频繁，请过几秒钟后重试",),
    RET.SERVER_ERROR: ("服务器异常",),
    RET.DB_ERR: ("数据库异常",),
    RET.DATE_ERROR: ("数据异常,请稍后重试",),
    RET.THIRD_ERROR: ("AI开小差了，请稍后重试一下吧~",),
    RET.INTEGRAL_ERROR: ("算力用尽了，请补充~",),
    RET.NO_DATE_ERROR: ("数据未找到",),
    RET.TP_ERR: ("请求超时,请稍后重试",),
    RET.MAX_TOKENS_ERR: ("已达最大对话内容，请换个对话框重试",),
    RET.AUTH_ERR: ("用户未登录",),
    RET.USER_ERR: ("用户信息获取失败",),
    RET.NOT_FOUND: ("数据未找到",),
    RET.LACK_ERROR: ("用户可试用次数不足",),
    RET.LACK_MAX_ERROR: ("你的会员次数已用完，请选择其他会话类型",),
    RET.NO_VIP: ("可用次数不足",),
    RET.NO_ITEM_ERROR: ("十分抱歉，您的余额已用完，请购买会员或流量包等产品",),
    RET.REASON_ERR: ("风险词汇",),
    RET.MAX_C_ERR: ("网络开小差了,请稍后重试吧~",),
    RET.MODEL_ERR: ("模型错误，请重新选择",),
    RET.KEY_ERR: ("key失效，请联系客服更换",),
    RET.MAX_RETRY_ERROR: ("最大重试失败",),
    RET.NO_NUMBER: ("次数已用完",),
}


class Language(object):
    _lang = 'zh_cn'

    @classmethod
    def init(cls, lang):
        cls._lang = lang

    @classmethod
    def get(cls, value):
        lang = language_pack.get(value)
        if not lang:
            return None
        if cls._lang == 'zh_cn' and len(lang) > 0:
            return lang[0]
        elif cls._lang == 'en_US' and len(lang) > 1:
            return lang[1]
        elif cls._lang == 'zh_F' and len(lang) > 2:
            return lang[2]
