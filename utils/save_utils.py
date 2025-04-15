#!/usr/bin/python3
# -*- coding: utf-8 -*-
# @Author: UMI
from django.db import transaction
from django.db.models import F

from apps.sc_chat.models.chat_models import CCChatSessionDtl, CCChatSession, DigitalClerkChat, CCChatImage, \
    CCChatImageDtl
from apps.sc_chat.utils import deduction_calculation, charges_api
from apps.sc_chat.models.group_chat_model import CgGroupChatDtl, CgGroupChat
from utils import constants
from utils.generate_number import set_flow
from utils.model_save_data import ModelSaveData


def save_image_task(session_code, content, chat_type, chat_group_code, save_list, user_code, source, size,
                    task_id="", integral=0, **kwargs):
    if not session_code:
        model = kwargs.get("model") or ""
        session_code = set_flow()
        CCChatSession.objects.create(
            session_code=session_code,
            title=content[:50],
            chat_type=chat_type,
            create_by=user_code,
            model=model
        )
    if not chat_group_code:
        chat_group_code = set_flow()
    for i in save_list:
        CCChatSessionDtl.objects.create(
            session_code=session_code,
            chat_group_code=chat_group_code,
            msg_code=set_flow(),
            role=i["role"],
            content=i["url"],
            covert_content=i.get("covert_content") or "",
            total_tokens=1,
            completion_tokens=0,
            prompt_tokens=0,
            create_by=user_code,
            action_type="3",
            source=source,
            size=size,
            task_id=task_id,
            integral=integral,
            is_mod=i.get("is_mod") or 0,
            status=i.get("status") or 0,
            images=i.get("images") or [],
        )


def save_image(user, chat_type, session_code, chat_group_code, content, create_by, save_list,
               action_type, source, size, task_id="", **kwargs):
        with transaction.atomic():
            integral = deduction_calculation(chat_type, 1)
            charges_api(user.user_code, integral, scene=constants.IMAGE_SCENE)

            if not session_code:
                session_code = set_flow()
                CCChatSession.objects.create(
                    session_code=session_code,
                    title=content[:50],
                    chat_type=chat_type,
                    create_by=create_by
                )
            if not chat_group_code:
                chat_group_code = set_flow()
            for i in save_list:
                CCChatSessionDtl.objects.create(
                    session_code=session_code,
                    chat_group_code=chat_group_code,
                    msg_code=set_flow(),
                    role=i["role"],
                    content=i["url"],
                    total_tokens=1,
                    completion_tokens=0,
                    prompt_tokens=0,
                    create_by=create_by,
                    action_type=action_type,
                    source=source,
                    size=size,
                    task_id=task_id,
                    integral=integral,
                    images=i.get("images") or [],
                )
        return session_code, chat_group_code


def save_image_v2(main_data, result_list, user_code):
    image_code = main_data.get("image_code")
    prompt = main_data.get("prompt") or ""
    main_data["title"] = prompt[:11] + "..."
    model_filter = ModelSaveData()

    main_save_data = model_filter.get_request_save_data(main_data, CCChatImage)
    main_save_data["create_by"] = user_code

    c_integral = 0
    with transaction.atomic():
        if not image_code:
            image_code = set_flow()
            main_save_data["image_code"] = image_code
            CCChatImage.objects.create(**main_save_data)

        for result in result_list:
            dtl_save_data = model_filter.get_request_save_data(result, CCChatImageDtl)
            dtl_save_data["image_code"] = image_code
            dtl_save_data["create_by"] = user_code
            CCChatImageDtl.objects.create(**dtl_save_data)
            c_integral += dtl_save_data.get("integral") or 0    # 总算力
        # 减少算力
        charges_api(user_code, c_integral, scene=constants.IMAGE_SCENE)
    return image_code


def save_session_v2(lod_msg_code, create_by, session_code, new_code, chat_type, chat_group_code, source, save_list, model="", **kwargs):
    data = kwargs.get("data") or {}
    image_url = data.get("image_url") or ""
    scenario_type = data.get("scenario_type") or ""
    clerk_code = data.get("clerk_code")
    company_code = data.get("company_code")
    with transaction.atomic():
        if lod_msg_code:
            save_list = save_list[1:]     # 重试，前面已经存过问题了无需再存
            CCChatSessionDtl.objects.filter(msg_code=lod_msg_code, create_by=create_by).update(is_delete=1)
        if not session_code:
            session_code = new_code
            content = save_list[0]["content"]
            CCChatSession.objects.create(
                session_code=session_code,
                title=content[:50],
                chat_type=chat_type,
                create_by=create_by,
                question_id=data.get("question_id", ""),
                model=model,
                image_url=image_url,
                scenario_type=scenario_type,
            )
        for i in save_list:
            msg_code = i.get("msg_code") or set_flow()
            CCChatSessionDtl.objects.create(
                session_code=session_code,
                chat_group_code=chat_group_code,
                msg_code=msg_code,
                finish_reason=i.get("finish_reason", ""),
                role=i["role"],
                content=i["content"],
                covert_content=i.get("covert_content", ""),
                total_tokens=i.get("total_tokens", 0),
                completion_tokens=i.get("completion_tokens", 0),
                prompt_tokens=i.get("prompt_tokens", 0),
                create_by=create_by,
                source=source,
                member_type=i.get("member_type", -1),
                integral=i.get("integral", 0),
                images=i.get("images") or [],
                origin_image=i.get("origin_image"),
                content_type=i.get("content_type"),
                agent_id=i.get("agent_id"),
            )

        if company_code and clerk_code:
            if not DigitalClerkChat.objects.filter(session_code=session_code).exists():
                DigitalClerkChat.objects.create(
                    clerk_code=clerk_code, company_code=company_code, session_code=session_code
                )
        return session_code


async def update_dtl(session_code, msg_code, content, total_tokens, prompt_tokens, integral, is_mod=0,
                     role="assistant", finish_reason="stop"):
    await CCChatSessionDtl.objects.filter(session_code=session_code, msg_code=msg_code).aupdate(
        finish_reason=finish_reason,
        role=role,
        content=content,
        total_tokens=total_tokens,
        completion_tokens=total_tokens - prompt_tokens,
        prompt_tokens=prompt_tokens,
        integral=integral,
        is_mod=is_mod,
    )


def save_group_chat(save_list, model_filter):
    """

    :param save_list:
    :param model_filter:
    :return:
    """

    insert_list = []

    save_list = model_filter.get_request_save_data(save_list, CgGroupChatDtl)
    for obj in save_list:
        insert_list.append(CgGroupChatDtl(**obj))
    CgGroupChatDtl.objects.bulk_create(insert_list)

    return


def update_group_chat(model_filter, msg_code, a_data, integral=0, session_code=""):
    up_data = model_filter.get_request_save_data(a_data, CgGroupChatDtl)

    with transaction.atomic():
        CgGroupChatDtl.objects.filter(msg_code=msg_code).update(
            **up_data
        )
        if integral > 0:
            CgGroupChat.objects.filter(session_code=session_code).update(
                use_integral=F('use_integral') - integral
            )
