# Starline Remake

Starline下载器的重构版本

## 使用

你**需要**运行fqweb项目（或与之API相同的项目）作为后端才能使用这个项目；
但是出于保护因素，fqweb项目**并未公开**

需要redis作为临时存储

1. 完成基础Python环境配置和依赖安装（如果你需要应用实现，还需要安装对应实现目录下的依赖）
2. 创建config.toml文件（和对应实现目录下的config.toml文件）并配置
3. 运行api.py和worker.py以及对应实现目录下的main.py

## 致谢

fqweb: [jingluopro](https://github.com/jingluopro) & [helloplhm-qwq](https://github.com/helloplhm-qwq)

## 许可证

GPLv3