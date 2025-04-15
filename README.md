<div align="center">

# 多模态平台

<br>

![platform multimodal](https://github.com/UMIntelligence/platform_multimodal/blob/main/assets/7ccaf2c1-9b72-41ae-9a89-5688c94b7abe.png)
</div>

![体验地址](https://ai.umi6.com)

**这是一个多模态平台.**


在启动项目前，请按照以下步骤完成环境准备：  


#### 一、配置项补全  
1. **定位配置项**：项目中所有待完成的配置项已通过 `TODO` 标记，支持主流 IDE 快速检索：  
   - **PyCharm**：左下角点击 `TODO` 面板查看标记项  
   - **VS Code**：通过快捷键 `Ctrl+Shift+O` 搜索 `TODO` 关键字  
   - 其他 IDE 可参考对应工具的 `TODO` 检索功能  

2. **配置要求**：请根据实际环境补全数据库连接、服务地址、认证信息等关键配置项  


#### 二、Python 环境准备  
- **版本要求**：必须使用 **Python 3.10** 版本  
- **验证方法**：  
  ```bash  
  python --version  # 确保输出 Python 3.10.x  
  ```  
- **环境建议**：推荐使用虚拟环境（如 `venv`/`conda`）隔离项目依赖  


#### 三、端口配置  
需提前在以下场景放行端口（确保无端口冲突）：  
- **防火墙规则**（Linux 示例）：  
  ```bash  
  sudo firewall-cmd --add-ports=28999/tcp --permanent  
  sudo firewall-cmd --add-ports=28998/tcp --permanent  
  sudo firewall-cmd --add-ports=28060/tcp --permanent  
  sudo firewall-cmd --add-ports=28083/tcp --permanent  
  sudo firewall-cmd --add-ports=28071/tcp --permanent  
  sudo firewall-cmd --add-ports=8080/tcp --permanent  
  sudo firewall-cmd --add-ports=29090/tcp --permanent  
  sudo firewall-cmd --reload  
  ```  
- **云服务器安全组**：在阿里云/腾讯云等平台的安全组配置中添加上述端口白名单  


#### 四、工作进程配置  
- **配置文件**：在项目启动脚本（通常为 `start.sh` 或 `start.py`）中，通过 `WORKERS` 参数自定义工作进程数量  
- **推荐配置**：根据服务器 CPU 核心数设置，建议值为 `CPU核心数 × 2 + 1`  


#### 五、OpenSearch 向量数据库准备  
支持两种部署方式（二选一）：  
##### 方案一：云端服务（推荐）  
- 选择阿里云 OpenSearch、亚马逊 OpenSearch Service 等云厂商服务  
- 完成实例创建后，记录 endpoint、认证信息等配置参数  

##### 方案二：本地 Docker 部署  
1. **下载配置文件**：确保项目根目录存在 `install_opensearch.yml` 文件  
2. **启动服务**：  
   ```bash  
   docker compose -f install_opensearch.yml build  # 首次构建镜像  
   docker compose -f install_opensearch.yml up -d   # 后台运行容器  
   ```  
3. **验证状态**：访问 `http://localhost:9200` 确认集群健康状态  


#### 六、Supervisor 进程管理  
1. **安装工具**：  
   - **Linux**：`sudo apt-get install supervisor`（Debian/Ubuntu）  
   - **Python 环境**：`pip install supervisor`  
2. **配置文件**：  
   - 将项目提供的 `supervisord.conf` 放置于默认配置目录（通常为 `/etc/supervisor/`）  
   - 或通过 `supervisord -c /path/to/supervisord.conf` 指定自定义配置路径  
3. **服务启动**：  
   ```bash  
   supervisorctl reload  # 重载配置  
   supervisorctl start all  # 启动所有管理进程  
   ```  


### 环境验证  
完成上述步骤后，可通过项目提供的自检脚本（如 `check_env.py`）或手动检查各服务端口连通性，确保所有依赖组件正常运行。

## 快速开始

### 环境准备
确保已安装 Docker 和 Docker Compose。

### 部署步骤
1. **拉取项目**  
   ```bash
   git clone https://github.com/UMIntelligence/platform_multimodal.git
   ```

2. **构建服务**  
   使用生产环境配置文件构建镜像：  
   ```bash
   docker compose -f production.yml build
   ```

3. **启动服务**  
   后台运行容器：  
   ```bash
   docker compose -f production.yml up -d
   ```

4. **状态检查**  
   通过容器 ID 查看日志（可先通过 `docker ps` 命令获取目标容器 ID）：  
   ```bash
   docker logs -f {containerId}
   # 无报错信息即表示服务运行正常
   ```


## 模块导航

### 多端及功能模块仓库
| 模块类型       | 模块名称       | 代码仓库链接                          | 说明                  |
|----------------|----------------|---------------------------------------|-----------------------|
| 前端平台       | PC 端前端      | [umi_platform_frontend](https://github.com/ymzn3820/umi_platform_frontend)       | PC 端前端代码仓库     |
|                | 小程序端       | [umi_platform_mini_program](https://github.com/ymzn3820/umi_platform_mini_program)    | 微信小程序代码仓库    |
|                | H5 端          | [umi_platform_h5](https://github.com/ymzn3820/umi_platform_h5)                     | H5 移动端代码仓库     |
| 后端功能模块   | 支付模块       | [umi_platform_pay_module](https://github.com/ymzn3820/umi_platform_pay_module)       | 支付系统核心模块      |
|                | 用户模块       | [umi_platform_user_module](https://github.com/ymzn3820/umi_platform_user_module)       | 用户中心服务模块      |
|                | Chat 模块      | [umi_platform_chat_module](https://github.com/ymzn3820/umi_platform_chat_module)      | 即时通讯核心模块      |

### 返回入口
[返回主项目引导页](https://github.com/ymzn3820/umi_platform_pay_module)  


## 许可证
本项目采用 **BSD 3-Clause License** 开源协议，详情见 [LICENSE](LICENSE) 文件。


