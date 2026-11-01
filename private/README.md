# 本地私有配置

此目录只用于保存本机运行所需的环境变量、测试凭据和临时配置，不提交到 Git。

建议创建 `sqlbot.local.env`，并通过下面的命令启动本地 Compose：

```powershell
docker compose --env-file private/sqlbot.local.env -f docker-local/compose.yaml up -d --build
```

至少需要提供：

```dotenv
SQLBOT_POSTGRES_USER=root
SQLBOT_POSTGRES_DB=sqlbot
SQLBOT_POSTGRES_PASSWORD=请在本机生成随机值
SQLBOT_DB_URL=postgresql+psycopg://root:请进行URL编码的密码@sqlbot-local-pg:5432/sqlbot
SQLBOT_SECRET_KEY=请在本机生成至少32字节的随机值
SQLBOT_DEFAULT_PWD=请在本机生成随机的初始管理员密码

# 密码包含特殊字符时，SQLBOT_DB_URL 中必须使用 URL 编码后的值。
```

不要把真实 API Key、数据库密码、JWT 密钥、数据库导出文件、日志或用户数据放入公开仓库。提交前请检查：

```powershell
git status --short --ignored
 git ls-files | Select-String -Pattern '(^|/)(\.env|private/|.*\.(db|sqlite|dump|sql|pem|key|p12|pfx|log))$'
```

`private/` 下的示例文件可以提交，真实配置文件必须保持忽略状态。
