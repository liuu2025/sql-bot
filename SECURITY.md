# 安全说明

## 不要提交的内容

请勿提交 API Key、JWT 密钥、数据库密码、私钥/证书、数据库导出、日志、浏览器会话、上传文件或真实客户数据。开发配置请放在被忽略的 `private/` 目录，并只提交不含真实值的 `.example` 文件。

提交前可检查：

```powershell
git status --short --ignored
git ls-files | Select-String -Pattern '(^|/)(\.env|private/|.*\.(db|sqlite|dump|sql|pem|key|p12|pfx|log))$'
```

## 本地运行边界

Docker Compose 端口默认只绑定到 `127.0.0.1`。本地单人模式和开发认证只适用于本机或可信网络，不能直接通过公网、反向代理或隧道暴露。

## 发现问题

如果误提交了密钥，请立即撤销/轮换该密钥，再删除文件。仅删除工作区文件不能清除 Git 历史中的值；公开仓库发布应使用不包含旧敏感历史的干净提交。
