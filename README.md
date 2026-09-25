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
4. **AirDuctCalibration（风道标定票）**：`garden`（所属茶园）、`calibrationDate`（标定日）、`windSpeed`（风速读数）、`passed`（是否通过）、`recorder`（记录人，建票时自动取当前登录用户）、`isVoided`（已作废）、`createdAt`

**业务规则**：

- 将槽位状态设为 `ready`（可下槽）时，若最新批次的 `actualMoisture` 为空或大于 40，抛出中文 `ValidationError`。
- 风道标定票：风速读数必须为正；同一茶园同一自然日只允许一张票，重复日拒绝并在表单回显已有票编号；未通过票与已作废票均不得当作有效。
- 槽位从 `loading`（装叶中）改为 `withering`（萎凋中）时，所属茶园必须存在有效标定——最新一张通过票未作废且标定日不早于七个自然日前；否则拒绝改态并中文提示缺少有效标定。校验在模型层（`Trough.clean`）强制执行，表单、后台、脚本任何保存路径都无法绕过。
- 有效判定共用函数：`apps/gardens/models.py` 的 `valid_calibration_qs()`。槽位改态校验（`garden_has_valid_calibration()`）、首页「有效标定茶园」统计、茶园列表 `?valid=1` 筛选均由它派生，三处口径必然一致。
- 权限：登录用户（含萎凋工 `witherer`）均可新建标定票；仅主管（超级用户，如 `admin`）可作废标定票，其余用户提交作废会被拒绝并提示。

## 页面

- 顶栏含「风道标定」入口：标定票列表（含有效/无效/已作废状态徽标）、新建标定票；主管可在列表直接作废。
- 首页统计卡含「有效标定茶园」数，点击可跳到茶园列表的有效筛选（`?valid=1`），两处行数一致。
- 茶园列表每行展示风道标定是否有效，并可一键筛选仅有效标定园。

## 种子数据

```bash
python manage.py seed_data
```

幂等：已有茶园则只保证账号存在。亦可在环境变量 `TEAWITHER_AUTO_SEED=1` 时于 `post_migrate` 自动播种。

种子含两张风道标定票：云雾岭一号园昨日通过（有效标定）；竹影台二号园仅有一张未通过票（无有效标定），用于演示「装叶中 → 萎凋中」被拦截的场景。二号园既有在制槽位为规则上线前的历史数据。

## 测试

```bash
python manage.py test
```

覆盖：风速必须为正、同园同日唯一并回显已有票号、未通过/已作废/超期票不算有效、装叶中→萎凋中改态拦截与放行、首页统计与茶园筛选一致、萎凋工可建票、非主管作废被拒。

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
