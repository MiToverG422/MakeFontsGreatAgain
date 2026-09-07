# Settings / Gboard 字体覆盖范围排查

这里的“未覆盖”指应用部分文字仍使用原字体外观，不等同于 Unicode 字符缺字。
以下结论来自一台 Android 16 类原生 ROM 的进程字体映射和安装包资源检查，
不是对所有 ROM、应用版本的承诺。

## 已发现的路径

| 应用 | 资源中明确引用的字体族 | 进程中映射的原系统字体 |
| --- | --- | --- |
| 设置 | google-sans-flex、variable-title-medium-emphasized、variable-title-large-emphasized 等 | /product/fonts/GoogleSansFlex-Regular.ttf |
| Gboard | variable-body-large、google-sans-flex、google-sans、google-sans-text 等 | /product/fonts/GoogleSansFlex-Regular.ttf、GoogleSans-Regular.ttf |

两个进程也映射了 MFGA 的主字体，因此并非模块完全没有挂载。进程映射只能证明
文件已加载，不能单独确定每个屏幕元素用了哪款字体；安装包中相应字体族引用
提供了进一步证据。

## 为什么绕过模块

`fonts_list.yaml` 将 `fonts_customization.xml` 列为黑名单，`search_dirs.sh` 会
保留它。该 ROM 的 `/product/etc/fonts_customization.xml` 中定义了独立的
Google Sans / Google Sans Flex / `variable-*` 字体族，指向 `/product/fonts`。
替换主 `sans-serif` 及其回退配置，不会自动替换这些命名字体族的首选字体。

Gboard 的部分 font-family 资源还设置了 `fontProviderSystemFontFamily`：

```text
variable-body-large
  → google-sans-flex
  → google-sans-text
```

同一资源同时声明 GMS 字体提供器。也就是说，系统命名字体族和 GMS 字体下载
是不同的入口。禁用 `com.google.android.gms.fonts` 不会移除已有的系统字体族，
因此不能保证 Gboard 的文字全部随主字体变化。

另外，检查到 Gboard 包含 `res/dMC.ttf` 及引用它的字体资源。尚未将该内置字体
对应到具体 UI 元素，不能把所有未覆盖的键帽都归因于这一个文件。

## 仓库 Xposed 入口的边界

当前建议作用域没有 Settings / Gboard。legacy 入口还有硬编码目标列表，
只在 LSPosed 中勾选额外应用并不能绕过这个列表。modern 入口没有同样的目标
列表，但依赖管理器授予作用域。

两种入口主要 Hook Builder / CustomFallbackBuilder / createFromAsset /
createFromFile，没有直接重定向 `Typeface.create(String, ...)` 的系统命名
字体族。因此“扩大作用域”也不等于完整解决系统字体族覆盖问题。

## 已实现的覆盖修复

安装时，`script/font_coverage.sh` 调用 `script/font_coverage.awk`，将 ROM 原有
`fonts_customization.xml` 中以下正文字体族转成指向 MFGA `sans-serif` 的别名：

- `google-sans`、`google-sans-flex`、`google-sans-text`。
- `google-sans-medium`、`google-sans-bold`。
- `variable-{body,title,headline,label,display}-{small,medium,large}` 及其
  `-emphasized` 版本。
- 指向上述被替换字体族的现有别名，包括 `google-sans-text-medium/bold`。

保留原名称，默认字重取原正体字体列表中最接近 400 的字重；例如
`variable-title-medium-emphasized` 保留 600，`google-sans-bold` 保留 700。
原有别名的显式字重也保留。之后字形、普通/粗体/斜体选择和多语言回退都使用
模块主字体链。模块缺少某个精确字重时，Android 仍会选择邻近可用字重。

例如：

```xml
<alias name="google-sans-flex" to="sans-serif" weight="400"/>
<alias name="variable-title-medium-emphasized" to="sans-serif" weight="600"/>
```

Android 会过滤目标不是实际命名字体族的别名，因此不能让原别名继续指向
新别名；脚本会把这些依赖也直接接到 `sans-serif`。重装时若读取到的系统
配置已经包含这些别名，仍会将它们复制进新模块，避免升级后覆盖失效。

解析器按 XML 标签及嵌套层级处理 `family` / `family-list`，支持多行标签、
单双引号、注释；不支持 DTD/CDATA 的输入会中止生成。生成到临时文件并成功后
才替换目标，错误不会写入半份 XML。非目标元素及注释保留。

`fonts_list.yaml` 的黑名单继续阻止把完整 `familyset` 复制到此文件；安装器在
黑名单判断之前进行上述专门处理。其他 `fonts-modification` 文件也不再被
通用复制逻辑覆盖。打包时除原有脚本和 `font_compat.sh` 外，还需将
`script/font_coverage.sh` 与 `script/font_coverage.awk` 放到模块根目录。

## 验证和边界

```sh
python3 -m unittest discover -s tests -v
```

覆盖测试包含嵌套列表、多行属性、默认字重、别名依赖、重复安装、非目标内容、
错误输入不改写目标，以及安装器对两种 XML 结构的分流。

在上述 Android 16 实机中，电脑和 Android awk 生成的配置 SHA-256 一致。
独立 `app_process` 进程用系统 `FontListParser` 读取候选配置，再构建系统
字体表：37 个目标名称的默认字重检查通过，中英文样例实际使用模块的
`400.ttf` / `700.ttf`；每个名称的 4 种样式均通过连续 4 次 `wght` / `ROND`
变体操作。此前六组 Noto 的崩溃修复必须同时保留。
实机安装重启后，挂载配置校验一致，直接加载系统字体表的选字/变体检查也通过；
Settings、Gboard 设置页及 Gemini 启动正常，验证窗口内没有新增崩溃记录。
Gboard 设置页截图中的中英文标题和列表已使用模块字体。使用者进一步确认
设置和 Gboard 键盘“都已覆盖，显示正常”。此结果仅代表本次实机和已检查页面。

这不是强制覆盖所有应用字体的 Hook。APK 内置字体、应用自行加载的下载字体、
Web 字体仍可能绕过系统字体表。`google-sans-clock`、`google-sans-flex-clock`、
其他 ROM 装饰/图标字体，以及显式命名的 `google-sans-text-*-italic` /
`google-sans-text-italic` 家族保持原定义；普通应用对已映射家族请求斜体则使用
模块字体链的斜体选择。Google Flex 的 ROND/opsz 等专属外观不会由别名保留，
是否支持这些轴取决于模块字体。当前不扩展 Settings/Gboard 的 Xposed 作用域。
