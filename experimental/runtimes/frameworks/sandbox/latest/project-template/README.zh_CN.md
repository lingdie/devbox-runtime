# Sandbox 框架示例

该模板提供一个多运行时的沙箱环境。

## 内置工具链

- Bun（最新版本）
- Node.js 22
- Python 3.14

## 运行方式

- 开发模式：`bash entrypoint.sh`
- 生产模式：`bash entrypoint.sh production`

默认服务监听 `8080` 端口，并以 JSON 返回当前运行时版本信息。
