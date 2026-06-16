import argparse

import requests

# 解析命令行参数：URL 与输出文件
parser = argparse.ArgumentParser(description="下载指定 URL 的纯文本 HTML 源码到本地文件。")
parser.add_argument("-u", "--url", default="http://www.ipp.cas.cn/",
                    help="要下载的网页 URL（默认: http://www.ipp.cas.cn/）")
parser.add_argument("-o", "--output", default="page.html",
                    help="保存的本地文件名（默认: page.html）")
args = parser.parse_args()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

try:
    response = requests.get(args.url, headers=headers, timeout=10)
    # 自动识别并设置正确的编码，防止中文乱码
    response.encoding = response.apparent_encoding

    # 将纯文本源码写入本地文件
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(response.text)

    print(f"【成功】纯文本 HTML 已下载至本地 {args.output}，无任何图片资产。")

except Exception as e:
    print(f"下载失败: {e}")