# 第一阶段：构建依赖项镜像10版本
FROM python:3.11-slim-buster AS builder

ADD ./sources.list /etc/apt/

# 修改 python 源
RUN echo "[global]\n\
index-url = https://pypi.tuna.tsinghua.edu.cn/simple\n\
\n\
[install]\n\
trusted-host=mirrors.aliyun.com\n\
           mirrors.aliyuncs.com\n\
           pypi.tuna.tsinghua.edu.cn\n\
           pypi.doubanio.com\n\
           pypi.python.org" > /etc/pip.conf

# 设置工作目录
WORKDIR /usr/src/app

# 复制 requirements.txt 文件
COPY requirements.txt .

RUN apt-get update && \
    apt-get install -y gcc build-essential

# 安装依赖项
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt

# 复制 alibabacloud-nls-python-sdk-1.0.0 目录
COPY utils/alibabacloud-nls-python-sdk-1.0.0 /tmp/nls-sdk

# 安装 alibabacloud-nls-python-sdk-1.0.0 包
RUN pip install --no-cache-dir --prefix=/install /tmp/nls-sdk


# 第二阶段：构建应用程序镜像
FROM python:3.11-slim-buster

# 修改 apt 源
ADD ./sources.list /etc/apt/

# 修改 python 源
RUN echo "[global]\n\
index-url = https://pypi.tuna.tsinghua.edu.cn/simple\n\
\n\
[install]\n\
trusted-host=mirrors.aliyun.com\n\
           mirrors.aliyuncs.com\n\
           pypi.tuna.tsinghua.edu.cn\n\
           pypi.doubanio.com\n\
           pypi.python.org" > /etc/pip.conf

# 安装所需的运行时库
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libpq5 \
        ffmpeg \
        supervisor \
        tzdata && \
    rm -rf /var/lib/apt/lists/*


COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
# 设置工作目录并复制依赖项
WORKDIR /usr/src/app
COPY --from=builder /install /usr/local

# 复制应用程序代码
COPY .. .

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/usr/bin:$PATH \
    PATH=/usr/src/app:$PATH

#EXPOSE 8999
EXPOSE 8000

# 配置 Gunicorn
#CMD ["gunicorn", "server_chat.asgi:application", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8999", "--workers=$(python -c 'import multiprocessing; print(multiprocessing.cpu_count() * 2 + 1)')"]
#CMD ["/usr/bin/supervisord"]
