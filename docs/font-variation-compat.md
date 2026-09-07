# 可变字体兼容修复

部分 Android 16 类原生 ROM 上，启用 MFGA 后，Gemini/Google 应用在创建
MaterialButton 时发生 `SIGSEGV`。本次实机调用栈为：

```text
Paint.setFontVariationSettings
Typeface.createFromTypefaceWithVariation
FontCollection::createCollectionWithVariation
FontFamily::FontFamily(parent, axes)
Font::isAxisSupported                  // null pointer, fault address 0x50
```

崩溃时正在检查 `ROND` 轴。它不是“不支持圆润度轴就应当崩溃”，也不能只凭
`SIGSEGV` 判断其他设备属于同一问题。

## 触发机制

同名的 `*-Regular.ttf` 在不同 ROM 中不一定是相同类型的字体：部分系统已经
将 Regular 换为可变字体，却仍保留静态的 `*-Bold.ttf`。MFGA 的旧配置会将
二者放入同一个回退组。

[AOSP Android 16 QPR2 的 FontFamily.cpp](https://android.googlesource.com/platform/frameworks/minikin/+/refs/heads/android16-qpr2-release/libs/minikin/FontFamily.cpp)
中，变体构造函数继承了父字体组的 `mFontsCount`，之后按支持轴筛选字体、
分配更短的数组，却没有同步更新数量。连续应用变体设置可能因此越界访问。
参考源码和实机调用栈相符，但不能据此认定所有 Android 版本都存在同一缺陷。

独立进程在原配置下依次调用：

```text
'wght' 500
'ROND' 100
'wght' 500, 'ROND' 100
'wght' 400
```

原配置在第三步发生段错误；修复后全部完成。单独设置不支持的 `ROND` 返回
`false` 属于正常结果。应用修复并重启后，Gemini 冷启动正常，用户确认可操作。

## 六处 XML 修改

以下 weight=700 的节点改用对应 Regular 文件，并加上
`<axis tag="wght" stylevalue="700"/>`。原有 `style`、`fallbackFor`、语言和顺序保留。

| 字体组 | 原文件 | 可变字体文件 |
| --- | --- | --- |
| 希伯来文 Serif | NotoSerifHebrew-Bold.ttf | NotoSerifHebrew-Regular.ttf |
| 泰文 Serif | NotoSerifThai-Bold.ttf | NotoSerifThai-Regular.ttf |
| 古吉拉特文 Sans | NotoSansGujarati-Bold.ttf | NotoSansGujarati-Regular.ttf |
| 奥里亚文 Sans | NotoSansOriya-Bold.ttf | NotoSansOriya-Regular.ttf |
| 老挝文 Sans | NotoSansLao-Bold.ttf | NotoSansLao-Regular.ttf |
| 老挝文 Serif | NotoSerifLao-Bold.ttf | NotoSerifLao-Regular.ttf |

例如：

```xml
<font weight="700" style="normal">NotoSansGujarati-Regular.ttf<axis tag="wght" stylevalue="700"/></font>
```

Regular 在此处是一个可生成多种字重的字体文件；显式选择 700 保留粗体效果。
没有修改字体二进制、Google APK 或系统 `libminikin.so`。

## 安装时兼容旧 ROM

`script/customize.sh` 在复制 XML 之前调用 `script/font_compat.sh`：

1. 优先检查本次模块中的 Regular 文件，其次检查 `/system/fonts` 下的文件。
2. 读取独立 TrueType/OpenType 字体的
   [`fvar` 表](https://learn.microsoft.com/en-us/typography/opentype/spec/fvar)，
   检查 `wght` 轴及范围是否包含 700。
3. 支持时使用可变 Regular；缺失、静态、不支持该字重或表结构无法识别时，
   将这六处恢复为原来的 Bold 引用。
4. 交给 `search_dirs.sh` 生成最终挂载的 XML。

该检查只解决这六个已确认的独立 SFNT 字体配对，不是通用字体校验器，也不
支持 TTC。它不需要在手机安装 Python、Java 工具链或额外原生可执行文件。
用户在 `fonts_list.yaml` 的 `reverse` 中提供的自定义 XML 不会由此脚本改写。

打包时与已有的 `customize.sh`、`search_dirs.sh` 一样，将 `script/font_compat.sh`
放到模块根目录；缺少此文件会让安装中止，避免跳过兼容检查。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

测试涵盖可变/静态 ROM、700 超出轴范围、缺失和截断字体、多轴、OpenType/CFF、
位于文件较后位置的 fvar、模块文件优先级、重复执行及保留 serif 回退属性。
Windows 可通过 `MFGA_TEST_SHELL` 指定 Git Bash。

另已在实机 Android shell 执行安装辅助函数，并让独立字体测试进程读取生成的
XML，成功完成原来的崩溃触发序列。系统、应用版本变化后仍需回归验证。
