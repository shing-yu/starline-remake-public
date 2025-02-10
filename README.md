# Starline Downloader Remake

Starline 下载器全新重制版。

## 介绍

Starline 下载器是一个用于下载番茄小说的项目；

基于由 [@jingluopro](https://github.com/jingluopro) 和 [@helloplhm-qwq](https://github.com/helloplhm-qwq) 开发的 fqweb 项目（闭源）的API实现内容获取。  
（[@hhhhhge](https://github.com/hhhhhge) 对以上项目进行了重构）

本项目无法在缺失 fqweb 的情况下部署。

## 使用

本项目的官方部署可通过以下方法使用
 - QQ群：690736066
 - Telegram：@Starline_book_bot

## 结构

本项目分为前后端结构：

后端：
 - worker.py  
   用于下载内容的后台进程
 - api.py  
   用于向不同前端提供API

官方实现的前端：
 - QQ官方机器人  
   基于 botpy 实现的QQ官方机器人，位于 `qqbot.offical` 目录下，该机器人有较多限制
 - Telegram官方机器人  
   基于 pyTelegramBotAPI 实现的Telegram官方机器人，位于 `tgbot` 目录下，该机器人限制较少

我们欢迎其他开发者实现更多前端

## 部署

本项目的部署需要 Python 3.10+ 版本

1. 安装后端和所需前端的依赖
2. 自行修改所有需要的`config.toml`文件
3. 运行`worker.py`和`api.py`
4. 运行前端

后台运行可自行实现或修改并复制所需的`.service`文件到`/etc/systemd/system/`目录下

## 许可证

本项目使用 GPL-3.0 许可证

## 贡献

我们欢迎任何贡献，欢迎开发者们提交PR  
特别欢迎开发者们实现更多前端
但因 fqweb 项目作者的要求，恕我们不能为各位提供测试环境

## 致谢

[@jingluopro](https://github.com/jingluopro)  
[@helloplhm-qwq](https://github.com/helloplhm-qwq)  
[@hhhhhge](https://github.com/hhhhhge)

![Github Education logo](https://user-images.githubusercontent.com/97467892/151880377-1c26ae86-8fbf-4874-9bb3-af7c7d050486.png#gh-light-mode-only)
感谢 [Github Education](https://education.github.com/) 提供的Github Pro和Github Copilot等免费服务

![Pycharm logo](https://raw.githubusercontent.com/JetBrains/logos/refs/heads/master/web/pycharm/pycharm-text.svg)  
感谢 [JetBrains](https://www.jetbrains.com/) 为学生提供的免费Pycharm Professional许可证


