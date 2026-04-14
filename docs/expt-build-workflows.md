# Experimental 镜像构建工作流

本文档说明以下两个 GitHub Actions 工作流的使用方式：

- `.github/workflows/build-all-expt-images-and-runtimes.yaml`
- `.github/workflows/build-expt-image-or-runtime.yaml`

它们对应 `experimental/images/` 和 `experimental/runtimes/` 下的构建流程，用于发布 experimental base images 与 runtime images。

## 什么时候用哪个工作流

### `build-all-expt-images-and-runtimes.yaml`

适合以下场景：

- 全量发布 experimental images + runtimes
- 构建某一类镜像，例如所有 language images
- 单独构建一个 framework runtime，并自动补齐上游依赖链

这是推荐的入口。它会先解析构建目标，再决定是否需要先构建：

- `base-tools`
- OS images
- language images
- framework images
- runtimes

### `build-expt-image-or-runtime.yaml`

适合以下场景：

- 只想构建某一层，例如只构建 `experimental/images/frameworks/...`
- 已经确认上游镜像存在，只想单独重跑某个 kind/build_type
- 作为 reusable workflow 被其他 workflow 调用

它不会自动推导完整依赖链，只会按传入的 `kind + name + build_type` 构建当前这一层。

## 推荐用法

### 1. 全量发布所有 experimental images 和 runtimes

在 `build-all-expt-images-and-runtimes.yaml` 中使用：

- `target_kind=all`
- `target_name=` 留空
- `target_build_type=all`
- `include_prerequisites=true`

### 2. 只构建所有 framework runtimes

- `target_kind=frameworks`
- `target_name=` 留空
- `target_build_type=runtimes`
- `include_prerequisites=true`

这会先构建 framework runtimes 需要的 framework images；如果上游 language/OS/tools 缺失，也会一起补齐。

### 3. 单独构建一个 framework runtime

例如构建 `experimental/runtimes/frameworks/nest.js/v11/Dockerfile`：

- `target_kind=frameworks`
- `target_name=nest.js/v11`
- `target_build_type=runtimes`
- `include_prerequisites=true`

这时工作流会自动规划并串行触发所需阶段。以 `nest.js/v11` 为例，当前依赖链会补齐到：

- `base-tools`
- `experimental/images/operating-systems/debian/12.6`
- `experimental/images/languages/node.js/20`
- `experimental/images/frameworks/nest.js/v11`
- `experimental/runtimes/frameworks/nest.js/v11`

这正是单个 framework runtime 最推荐的触发方式。

### 4. 只重跑某个 image，不补前置

例如只重跑 `experimental/images/languages/node.js/20/Dockerfile`：

- `target_kind=languages`
- `target_name=node.js/20`
- `target_build_type=images`
- `include_prerequisites=false`

这种模式适合你已经确认上游镜像都在 registry 中可用，只想重建当前目标本身。

### 5. 只重跑某个 runtime，不补前置

例如只重跑 `experimental/runtimes/frameworks/openclaw/latest/Dockerfile`：

- `target_kind=frameworks`
- `target_name=openclaw/latest`
- `target_build_type=runtimes`
- `include_prerequisites=false`

注意：这要求它依赖的 base image 已经存在于目标 registry 中，否则构建会在 `FROM` 阶段失败。

## 关键输入说明

### `tag`

最终镜像 tag 的主版本号。大多数场景直接传本次发布版本，例如：

- `v0.0.1-alpha.2`
- `2026-04-14`
- `latest`

### `tools_version`

仅在需要复用已存在的 `base-tools` 时覆盖。留空时默认跟随 `tag`。

### `os_version`

仅在需要复用已发布的 experimental OS image 时覆盖。留空时默认跟随 `tag`。

### `framework_image_version`

仅在 runtime 构建时需要复用已存在 framework image 时覆盖。留空时默认跟随 `tag`。

### `target_kind`

控制当前构建要聚焦哪一类：

- `all`
- `operating-systems`
- `languages`
- `frameworks`

### `target_name`

可选的精确目标路径，格式是 `kind` 下的相对子路径，不带 `experimental/...` 前缀，也不带 `Dockerfile`。

示例：

- `debian/12.6`
- `ubuntu/22.04`
- `node.js/20`
- `python/3.12`
- `nest.js/v11`
- `openclaw/latest`

### `target_build_type`

- `all`: images + runtimes 都构建
- `images`: 只构建 `experimental/images`
- `runtimes`: 只构建 `experimental/runtimes`

### `include_prerequisites`

这是新的关键开关：

- `true`: 自动构建所需上游依赖，适合手动触发单个 runtime
- `false`: 只构建当前目标，适合重跑单层任务

如果你不确定选哪个，优先用 `true`。

### `l10n`

- `en_US`
- `zh_CN`
- `both`

### `arch`

- `amd64`
- `arm64`
- `both`

### `aliyun_enabled`

开启后会执行：

- Aliyun ACR 登录
- Aliyun 镜像 tag 生成
- Aliyun 镜像 push
- Aliyun manifest 创建

如果不开启，则只推送到 GHCR。

## 阿里云推送需要的 Secrets

`build-expt-image-or-runtime.yaml` 通过 reusable workflow 方式接收以下 secrets：

- `ALIYUN_REGISTRY`
- `ALIYUN_USERNAME`
- `ALIYUN_PASSWORD`
- `ALIYUN_NAMESPACE`

推荐检查以下几点：

- `ALIYUN_REGISTRY` 是实际 registry 地址，例如 `registry.cn-hangzhou.aliyuncs.com`
- `ALIYUN_NAMESPACE` 是命名空间，不要把仓库名一并写进去
- 用户名和密码对应的是能 push 目标命名空间的账号
- 在 workflow dispatch 时显式打开 `aliyun_enabled=true`

## 镜像命名约定

当前 experimental workflow 会按构建类型写入不同仓库：

- `images` -> `ghcr.io/<owner>/devbox-base-expt/...`
- `runtimes` -> `ghcr.io/<owner>/devbox-runtime-expt/...`

阿里云开启后也会沿用相同的镜像名层级，只是 registry 和 namespace 不同。

## 常见问题

### 为什么以前单独构建一个 framework runtime 要手动跑很多次

因为 runtime 自身只构建当前层，但它的 `FROM` 会引用 framework image；framework image 又可能引用 language image；language image 再引用 OS image 和 `base-tools`。如果工作流不帮你补前置，就只能手动逐层跑。

现在推荐直接用：

- `build-all-expt-images-and-runtimes.yaml`
- `target_kind=frameworks`
- `target_name=<framework>/<version>`
- `target_build_type=runtimes`
- `include_prerequisites=true`

### 为什么只开了阿里云开关，但没有推送成功

通常优先检查：

- 是否真的勾选了 `aliyun_enabled`
- 相关 Aliyun secrets 是否都已配置
- 命名空间和 registry 是否匹配
- 当前 tag 下的多架构分片是否先成功构建

如果前面的 per-arch 镜像没有推送成功，manifest 阶段也不会成功。

### `target_name` 应该填什么

填 `experimental/images/<kind>/` 或 `experimental/runtimes/<kind>/` 之后的子路径。

不要填：

- `experimental/images/frameworks/nest.js/v11/Dockerfile`

应该填：

- `nest.js/v11`

## 建议

如果目标是“我就想把一个 framework runtime 发出来”，优先使用：

- `build-all-expt-images-and-runtimes.yaml`
- `target_build_type=runtimes`
- `include_prerequisites=true`

如果目标是“我知道依赖都在，只重跑这一层”，再使用：

- `build-expt-image-or-runtime.yaml`

