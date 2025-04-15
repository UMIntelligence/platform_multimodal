#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI


def get_client_ip(request):
    """
    获取ip
    :param request:
    :return:
    """
    try:
        real_ip = request.META['HTTP_X_FORWARDED_FOR']
        regip = real_ip.split(",")[0]
    except:
        try:
            regip = request.META['REMOTE_ADDR']
        except:
            regip = ""
    return regip
