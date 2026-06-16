# test urls

url: http://www.ipp.cas.cn/


```python 
import requests
from bs4 import BeautifulSoup

url = "http://www.ipp.cas.cn/"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
response = requests.get(url, headers=headers)
response.encoding = 'utf-8' # 确保中文不乱码
soup = BeautifulSoup(response.text, 'html.parser')

# 核心定位：找到文本为“通知公告”的 H2 或 H3 标签，再获取它同级或下方的 ul 列表
# 方式 A：通过文本内容模糊匹配定位
notice_title = soup.find(lambda tag: tag.name in ['h2', 'h3', 'div'] and '通知公告' in tag.text)
if notice_title:
    # 顺着标题找到紧跟在后面的 ul 列表（或者包裹列表的 div）
    notice_list = notice_title.find_next('ul')
    
    for li in notice_list.find_all('li'):
        title = li.find('a').text.strip()
        link = li.find('a')['href']
        # 有的网站日期在 span 里，有的直接在 li 文本中
        date = li.find('span').text.strip() if li.find('span') else "" 
        
        print(f"日期: {date} | 标题: {title} | 链接: {link}")
```

```XQuery
//*[contains(text(), '通知公告')]/ancestor::div[1]//ul/li/span
```


actually, from ipp_page.html, we can find it in 
```html
<div class="ipp2020-container">
	<div class="wx-col-z wx-mb25">
		<div class="g-in clearfix">
            <div class="fl">
                <div class="ipp2020-item ipp2020-item-4">
                    <div class="hd">
                        <h2>通知公告</h2>
```