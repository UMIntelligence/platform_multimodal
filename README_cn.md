# Multimodal Platform
<p align="center">
  <a href="./README_cn.md">English</a> |
  <a href="./README.md">简体中文</a> 
</p>
<div align="center">
  <br>
  <img src="https://github.com/UMIntelligence/platform_multimodal/blob/main/assets/7ccaf2c1-9b72-41ae-9a89-5688c94b7abe.png" alt="platform multimodal">
</div>

**Experience Address**: [https://ai.umi6.com](https://ai.umi6.com)

**Introduction**: This is a multimodal platform. Before starting the project, please complete the environment preparation according to the following steps.

## Environment Preparation Steps

### 1. Completion of Configuration Items
1. **Locate Configuration Items**: All pending configuration items in the project are marked with `TODO`. Mainstream IDEs support quick retrieval:
    - **PyCharm**: Click the `TODO` panel at the bottom left to view the marked items.
    - **VS Code**: Use the shortcut key `Ctrl + Shift + O` to search for the `TODO` keyword.
    - **Other IDEs**: Refer to the `TODO` retrieval function of the corresponding tool.
2. **Configuration Requirements**: Please complete key configuration items such as database connections, service addresses, and authentication information according to the actual environment.

### 2. Preparation of Python Environment
- **Version Requirement**: You must use **Python 3.10**.
- **Verification Method**:
```bash
python --version  # Ensure the output is Python 3.10.x
```
- **Environment Recommendation**: It is recommended to use a virtual environment (such as `venv` or `conda`) to isolate project dependencies.

### 3. Port Configuration
You need to release the ports in advance in the following scenarios to ensure there are no port conflicts:
- **Firewall Rules (Linux Example)**:
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
- **Cloud Server Security Group**: Add the above port whitelist to the security group configuration on platforms such as Alibaba Cloud and Tencent Cloud.

### 4. Worker Process Configuration
- **Configuration File**: In the project startup script (usually `start.sh` or `start.py`), customize the number of worker processes through the `WORKERS` parameter.
- **Recommended Configuration**: Set it according to the number of CPU cores of the server. The recommended value is `Number of CPU cores × 2 + 1`.

### 5. Preparation of OpenSearch Vector Database
Two deployment methods are supported. You can choose one of them:
#### Option 1: Cloud Service (Recommended)
Choose cloud provider services such as Alibaba Cloud OpenSearch or Amazon OpenSearch Service. After creating the instance, record the configuration parameters such as the endpoint and authentication information.

#### Option 2: Local Docker Deployment
1. **Download Configuration File**: Ensure that the `install_opensearch.yml` file exists in the project root directory.
2. **Start the Service**:
```bash
docker compose -f install_opensearch.yml build  # Build the image for the first time
docker compose -f install_opensearch.yml up -d  # Run the container in the background
```
3. **Verify the Status**: Access `http://localhost:9200` to confirm the cluster health status.

### 6. Supervisor Process Management
1. **Install the Tool**:
    - **Linux**: Use `sudo apt-get install supervisor` (Debian/Ubuntu).
    - **Python Environment**: Use `pip install supervisor`.
2. **Configuration File**:
    - Place the provided `supervisord.conf` in the default configuration directory (usually `/etc/supervisor/`).
    - Or specify a custom configuration path through `supervisord -c /path/to/supervisord.conf`.
3. **Start the Service**:
```bash
supervisorctl reload  # Reload the configuration
supervisorctl start all  # Start all managed processes
```

## Environment Verification
After completing the above steps, you can use the self-check script provided by the project (such as `check_env.py`) or manually check the connectivity of each service port to ensure that all dependent components are running normally.


## 🎉 Stay Tuned

⭐️ Star our repository to stay up-to-date with exciting new features and improvements! Get instant notifications for new
releases! 🌟

<div align="center" style="margin-top:20px;margin-bottom:20px;">
<img src="https://github.com/UMIntelligence/platform_multimodal/blob/main/assets/3ed4e296-fbf2-4618-9011-8eca26fe3461.gif" width="1200"/>
</div>

## Quick Start

### Prerequisites
Ensure that Docker and Docker Compose are installed.


### Deployment Steps
1. **Pull the Project**
```bash
git clone https://github.com/UMIntelligence/platform_multimodal.git
```
2. **Build the Service**
Build the image using the production environment configuration file:
```bash
docker compose -f production.yml build
```
3. **Start the Service**
Run the container in the background:
```bash
docker compose -f production.yml up -d
```
4. **Status Check**
View the logs through the container ID (you can first obtain the target container ID through the `docker ps` command):
```bash
docker logs -f {containerId}
# No error message indicates that the service is running normally
```

## Module Navigation

### Repositories of Multi - Terminal and Functional Modules
| Module Type      | Module Name      | Code Repository Link                          | Description           |
|------------------|------------------|-----------------------------------------------|-----------------------|
| Front - end Platform | PC Front - end   | [platform_multimodal_frontend](https://github.com/UMIntelligence/platform_multimodal_frontend)       | PC front - end code repository |
|                  | Mini - Program   | [umi_platform_mini_program](https://github.com/ymzn3820/umi_platform_mini_program)    | WeChat mini - program code repository |
|                  | H5 Terminal      | [umi_platform_h5](https://github.com/ymzn3820/umi_platform_h5)                     | H5 mobile - end code repository |
| Back - end Functional Modules | Payment Module   | [umi_platform_pay_module](https://github.com/ymzn3820/umi_platform_pay_module)       | Core module of the payment system |
|                  | User Module      | [umi_platform_user_module](https://github.com/ymzn3820/umi_platform_user_module)       | User center service module |
|                  | Chat Module      | [platform_multimodal](https://github.com/UMIntelligence/platform_multimodal)      | Core module of instant messaging |

### Return Entry
[Return to the Main Project Guide Page](https://github.com/ymzn3820/umi_platform_pay_module)

## License
This project uses the **BSD 3 - Clause License** open - source license. For details, see the [LICENSE](LICENSE) file.



