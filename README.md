# TeaWither-01 · 茶萎凋台账

Django 5 + PostgreSQL 服务端渲染应用：Templates + HTMX + 自定义 CSS，无 Vue/React SPA。

## 技术栈

- Django 5、PostgreSQL
- Session 登录
- HTMX（CDN）局部刷新列表
- Docker Compose：`web` + `db`

## 端口与数据库

| 服务 | 端口 |
|------|------|
| Web  | **4100** |
| Postgres | **5440**（容器内 5432） |

数据库账号：`teawither` / `teawither` / 库名 `teawither`

## 快速启动

```bash
cd TeaWither/TeaWither-01
docker compose up --build -d
```

浏览器打开：http://localhost:4100

演示账号：

- `admin` / `123456`（超级用户）
- `witherer` / `123456`（普通用户）

容器启动时会自动：`migrate` → `seed_data` → `collectstatic` → `gunicorn`

## 本地开发（可选）

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
pip install -r requirements.txt
# 确保本机 Postgres 监听 5440，或先 docker compose up -d db
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5440
python manage.py migrate
python manage.py seed_data
python manage.py runserver 0.0.0.0:4100
```

## 业务模型

1. **Garden（茶园）**：`name`、`altitudeBand`、`notes`
2. **Trough（萎凋槽）**：归属茶园、`troughCode`、`cultivar`、`loadKg`、状态 `loading|withering|ready`；同一茶园内槽位编号唯一
3. **WitherBatch（萎凋批次）**：归属槽位、`startedAt`、`targetMoisture`、`actualMoisture`（可空）、`rollGrade`
4. **AirDuctCalibration（风道标定票）**：`garden`（所属茶园）、`calibrationDate`（标定日）、`windSpeed`（风速读数，必须为正）、`passed`（是否通过）、`recordedBy`（记录人）

**业务规则**：

- 将槽位状态设为 `ready`（可下槽）时，若最新批次的 `actualMoisture` 为空或大于 40，抛出中文 `ValidationError`。
- 槽位仅当**所属茶园持有有效风道标定**时，才允许由 `loading`（装叶中）改为 `withering`（萎凋中），否则拒绝改态并中文提示「缺有效标定」。有效标定定义（改态判定与列表/首页筛选共用 `models.valid_calibration` / `models.has_valid_calibration`）：
  - 该园**最新一张**标定票（按标定日）必须存在且 `passed=True`——未通过票不得当作有效，其后也不能用更早的通过票；
  - 标定日不早于七个自然日前（票龄 ≤ 7 个自然日，过期即无效）。
- 同一茶园同一自然日只允许一张标定票（数据库唯一约束 + 表单校验）；重复建票被拒绝并回显已有票标识（如 `#12（茶园 · 日期 · 通过）`）。
- 风速读数必须为正数（模型层与表单层双重校验）。

## 权限

- 萎凋工（任意已登录用户，如 `witherer`）可新建风道标定票，记录人自动取当前用户。
- 作废（删除）标定票仅**主管**（`is_staff`，如超级用户 `admin`）可执行；其余用户访问作废链接一律返回 403。

## 页面

- 顶栏新增「风道标定」：标定票列表（可按茶园筛选）、新建、作废。
- 首页新增「有效标定园数」统计卡，点击直达茶园列表 `?valid=1`；该计数与「仅看有效标定园」筛选结果行数一致（同一判定函数）。
- 茶园列表可切换「仅看有效标定园」，并展示每园当前标定状态（有效/无有效标定）。

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有茶园则只保证账号存在。亦可在环境变量 `TEAWITHER_AUTO_SEED=1` 时于 `post_migrate` 自动播种。

种子含两个茶园：云雾岭一号园有一张当日通过的风道标定票（有效，槽可进入萎凋中），竹影台二号园无任何标定票（无有效标定，槽不得由装叶中改为萎凋中）。

## 目录结构

```
TeaWither-01/
  manage.py
  requirements.txt
  Dockerfile
  entrypoint.sh
  docker-compose.yml
  config/           # 项目配置
  apps/gardens/     # 模型、视图、种子命令
  templates/        # Django 模板
  static/css/       # 自定义样式（茶绿色顶栏）
```
