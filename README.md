# 良心商家

查询「商家对员工好不好」的一期可运行实现：编辑加工公开信息为主体，用户打分为佐证。

## 本地运行（推荐，无需 Docker）

依赖：Python 3.12+、Node 18+。本仓库默认 **SQLite + 进程内任务队列**，不需要 Postgres / Redis / 微信正式资质。

```bash
# 1. 后端
cd backend
pip install -r requirements.txt
python -m app.seed          # 导入 13 个品牌、18 条依据、4 个案例
uvicorn app.main:app --reload --port 8000

# 2. 用户端 H5（按微信小程序交互，浏览器即可检查）
cd ../web && npm install && npm run dev     # http://localhost:5173

# 3. 运营后台
cd ../admin && npm install && npm run dev   # http://localhost:5174
# 账号 admin / admin123
```

或 `bash scripts/dev.sh` 一次拉起。

### 用微信开发者工具打开原生小程序

打开 `miniprogram/` 目录。开发者工具勾选「不校验合法域名、HTTPS」。`utils/request.js` 里 `BASE` 默认 `http://127.0.0.1:8000/api/v1`。真机预览需内网穿透。

## 目录

| 路径 | 说明 |
|---|---|
| `docs/整体方案设计.md` | 产品与技术方案 |
| `backend/` | FastAPI：`/api/v1` 小程序端、`/admin/v1` 后台、采集管道、评级引擎 |
| `web/` | 用户端 H5，组件库 **antd-mobile** |
| `admin/` | 运营后台，组件库 **Ant Design + ProComponents** |
| `miniprogram/` | 微信原生小程序（与 H5 同一套接口） |

## 一期自动化边界

采集 / LLM 抽取 / 实体匹配 / 评级 / 卡片渲染自动跑。负面依据：正向与 **A 级**自动发布，B/C 级进审核队列（`AUTO_PUBLISH_POLICY`）。LLM 未配置时走关键词规则 mock，保证离线可跑通。

## 生产部署

见方案第 13 节。最小形态：一台云服务器 + `docker compose` + 已备案域名 + HTTPS + 腾讯云 COS。把 `.env` 中的 `DATABASE_URL` 换成 Postgres、`REDIS_URL` 填上后，`CELERY_EAGER=false` 即可拆出独立 worker。
