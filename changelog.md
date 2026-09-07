CN

17.0.1.08-31-alpha2-fix(1717180004)
 - 修复部分 Android 16 ROM 中六组 Noto 静态/可变字体混用触发的字体变体闪退。
 - 安装时检查 Regular 字体的 fvar/wght 范围；旧系统保留静态 Bold 引用。
 - 修复 Settings / Gboard 等应用通过 Google Sans / Flex / Material variable 正文字体族绕过主字体的问题；安装时定向生成 OEM 字体别名，保留默认字重和其他自定义字体。
 - 保留 fonts-modification 配置结构，避免把 ROM 的字体定制 XML 错误覆盖为 familyset。
 - 基于上游 SELFUSE 版打包，保留字体和原生组件，模块版本增加 -fix；本次不包含 Xposed APK 或 Telegram 专用适配。
 
17.0.1.08-31-alpha2(1717180003)
 - 1.适配HyperOS4
 - 2.同步/新增部分字体，调整部分私用区符号颜色
 - 3*.新增Xposed版本MFGA覆盖一些内置了字体的应用
 - 4.增加了对部分Unicode18彩色Emoji的初步支持(早期预览版)
```
🛙🪋🪌🪍🫌🫝🫫🫹🫺
```
 
17.0.0.06-27-alpha(1717180001)
 - 1.同步Roboto到3.0.16(SU)
 - 2.WebUI新增主字体上色，需支持COLRv0，Android10及以上
 - 3.调整主字体中部分组合类符号，修复缺失、在高安卓版本显示异常的情况
 

-------
EN
 
17.0.1.08-31-alpha2(1717180003)
 - 1.Added support for HyperOS 4
 - 2.Synced/Added some fonts and adjusted the colors of some Private Use Area symbols
 - 3*.Added an Xposed version of MFGA to override fonts in some apps with built-in fonts
 - 4.Added preliminary support for some Unicode 18 colored emoji (early preview)
```
🛙🪋🪌🪍🫌🫝🫫🫹🫺
```
 
17.0.0.06-27-alpha(1717180001)
 - 1.Synchronized Roboto font to version 3.0.16(SU).
 - 2.Added main font colorization in WebUI; requires COLRv0 support, Android 10 and above.
 - 3.Adjusted some composite symbols in the main font, fixing missing glyphs and display issues on higher Android versions.
 

Telegram channel:

https://t.me/AndroidCoreLayer

Power by:

Yiyunlengyu(酷安@Numbersf)
