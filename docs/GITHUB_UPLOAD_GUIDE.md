# GitHub 上传说明

本说明用于将 Q-Explorer 公开为竞赛代码仓库。发布包不包含 `.venv`、缓存、`.env` 或 Git 元数据，但包含源码、测试、冻结配置、报告、聚合结果和可审计 traces。

## 推荐方法：保留现有 Git 历史

1. 在 GitHub 网页创建一个空的公开仓库，例如 `q-explorer`。
2. 不要勾选自动生成 README、`.gitignore` 或 License。
3. 在本机原项目目录打开 PowerShell：

```powershell
cd "D:\GOAL世界人工智能开源大赛\q-explorer"
git remote add origin https://github.com/<你的用户名>/q-explorer.git
git push -u origin v05-gate0-mobilecloud-hardware-audit:main
```

4. 在 GitHub 仓库设置中确认默认分支为 `main`。

Git 首次推送时可能通过 Git Credential Manager 打开浏览器认证。不要在命令、仓库文件或聊天中粘贴访问令牌。

## 使用发布压缩包

解压 `Q-Explorer_GitHub_Release.zip` 后，可将解压目录初始化为新的干净仓库：

```powershell
git init -b main
git add .
git commit -m "publish Q-Explorer competition release"
git remote add origin https://github.com/<你的用户名>/q-explorer.git
git push -u origin main
```

这种方式只包含发布快照，不保留 V0.1–V0.5 的历史提交。若评审重视预注册提交和历史可追溯性，优先使用第一种方法。

## 发布前检查

```powershell
python -m pytest -q
git status -sb
git ls-files | Select-String -Pattern '(^|/)\.env$'
```

确认：

- 测试通过；
- 没有提交 `.env`；
- 没有 API key、云平台 access key 或 secret key；
- 仓库可见性满足比赛评审要求；
- README 首页能够正常显示 `results/v04/figures/figure1_scientific_boundary_rate.png`。

