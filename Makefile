# RSSRob —— 目标约定见 Felix2yu/.github/docs/makefile.md
#
# 七个必备目标：build / dev / test / lint / fmt / docker / clean
# 其余目标按仓库自身需要添加。
.PHONY: build dev test lint lint-strict fmt docker clean

VENV := .venv
PY   := $(VENV)/bin/python

## 建虚拟环境并装依赖（不装进系统 Python）。两个 requirements：核心 + Flask 管理界面
build:
	python3 -m venv $(VENV)
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements.txt -r requirements-web.txt

dev: build
	$(PY) -m rssrob

## pytest 是开发依赖，不进 requirements.txt（那是运行时装的），按 CI 的做法临时装
test: build
	$(PY) -m pip install -q pytest
	$(PY) -m pytest -q

## 没有引入 linter，只做语法编译检查（能挡住真正的语法错误）
lint:
	$(PY) -m compileall -q rssrob

fmt:
	@echo "未引入格式化工具；如需统一风格，先讨论再引入 black/ruff-format"

docker:
	docker build -t rssrob:dev .

clean:
	rm -rf $(VENV) .pytest_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
