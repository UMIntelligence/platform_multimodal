<div align="center">

# 多模态平台
**这是一个多模态平台.**


[![Website][website-shield]][website-url]
[![Dynamic JSON Badge][discord-shield]][discord-url]
[![Matrix][matrix-shield]][matrix-url]
<br>

![platform multimodal](https://github.com/UMIntelligence/platform_multimodal/assets/7ccaf2c1-9b72-41ae-9a89-5688c94b7abe.png)
</div>

ComfyUI lets you design and execute advanced stable diffusion pipelines using a graph/nodes/flowchart based interface. Available on Windows, Linux, and macOS.

# 多模态平台

![体验地址](https://umi-intelligence.oss-cn-shenzhen.aliyuncs.com/static/website/screenshot-ai.umi6.com-2024.03.13-10_15_32.png)

## 准备工作

请按照以下步骤准备环境：

- **配置项**：补全相关配置项。这些配置项已经以`TODO`形式列出。在Pycharm中，可在左下角点击`TODO`展示，其他IDE操作类似。
- **Python版本**：请确保使用的是Python 3.10版本。
- **端口放行**：确保以下端口已放行：28999、28998、28060、28083、28060、 28071、 8080、 29090。
- **工作进程**：在`start`中自行配置工作进程的数量。
- **Opensearch数据库**：需要提前准备好opensearch向量数据库。你可以选择购买云服务或者本地安装。本地安装参考命令如下：
  ```sh
  docker compose -f install_opensearch.yml build 
  docker compose -f install_opensearch.yml up -d
- **Supervisor**：需要提前准备Supervisor。配置文件 supervisord.conf


## 开始
    拉取项目：git clone https://github.com/ymzn3820/umi_platform_chat_module.git
    构建：docker compose -f production.yml build
    运行：docker compose -f production.yml up -d
    检查：docker logs -f {containerId}, 如果没有报错信息，则运行成功。

## 导航
| 模块名称 | 链接 | 介绍|
| -------- | ---- |---- |
| 前端PC | [umi_platform_frontend](https://github.com/ymzn3820/umi_platform_frontend) | PC端前段代码仓库地址|
| 小程序端 | [umi_platform_mini_program](https://github.com/ymzn3820/umi_platform_mini_program) |小程序端代码仓库地址|
| H5端 | [umi_platform_h5](https://github.com/ymzn3820/umi_platform_h5) |H5端代码仓库地址|
| 支付模块 | [umi_platform_pay_module](https://github.com/ymzn3820/umi_platform_pay_module) |支付模块代码仓库地址|
| 用户模块 | [umi_platform_user_module](https://github.com/ymzn3820/umi_platform_user_module) |用户模块代码仓库地址|
| Chat模块 | [umi_platform_chat_module](https://github.com/ymzn3820/umi_platform_chat_module) |Chat模块代码仓库地址|

[返回引导页](https://github.com/ymzn3820/umi_platform_pay_module)

## License

BSD 3-Clause License
