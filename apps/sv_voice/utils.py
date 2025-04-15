#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
import asyncio
import json

from server_chat import settings


async def send_start_params(ws, dev_pid, format_str):
    """
    开始参数帧
    :param websocket.WebSocket ws:
    :param dev_pid:
    :param format_str:
    :return:
    """
    req = {
        "type": "START",
        "data": {
            "appid": settings.B_APP_ID,  # 网页上的appid
            "appkey": settings.B_APP_KEY,  # 网页上的appid对应的appkey
            "dev_pid": dev_pid,  # 识别模型
            "cuid": "yourself_defined_user_id11",  # 随便填不影响使用。机器的mac或者其它唯一id，百度计算UV用。
            "sample": 16000,  # 固定参数
            "format": "pcm"  # 固定参数
        }
    }
    body = json.dumps(req)
    await ws.send(body)


async def send_audio(ws, bytes_data):
    """
    发送二进制音频数据，注意每个帧之间需要有间隔时间
    :param  websocket.WebSocket ws:
    :param  bytes_data: 二进制音视频文件
    :return:
    """
    chunk_ms = 160  # 160ms的录音
    chunk_len = int(16000 * 2 / 1000 * chunk_ms)
    print("------传输")
    index = 0
    total = len(bytes_data)
    while index < total:
        end = index + chunk_len
        if end >= total:
            # 最后一个音频数据帧
            end = total
        body = bytes_data[index:end]
        await ws.send(body)
        index = end
        await asyncio.sleep(chunk_ms / 1000.0)  # ws.send 也有点耗时，这里没有计算


async def send_finish(ws):
    """
    发送结束帧
    :param websocket.WebSocket ws:
    :return:
    """
    req = {
        "type": "FINISH"
    }
    body = json.dumps(req)
    await ws.send(body)
