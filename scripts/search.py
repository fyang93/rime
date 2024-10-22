import re
import asyncio
import aiofiles
from pyppeteer import launch


async def search_flypy(queries):
    options = {
      "executablePath": r"/run/current-system/sw/bin/chromium",
      "headless": False,
      "defaultViewport": {"width": 1920, "height": 1080},
      "autoClose": True,
      "dumpio": True,
      "args": [
          "--no-sandbox",
          "--disable-infobars",
      ]
    }

    browser = await launch(**options)
    page = await browser.newPage()
    await page.goto('http://react.xhup.club/search')
    await asyncio.sleep(2)

    async with aiofiles.open('./dicts/chaizi_flypy.txt', 'w') as f:
        for char in queries:
            await page.type(selector='#__next > div > div:nth-child(1) > div.div-1 > input', text=char)
            await page.click(selector='#__next > div > div:nth-child(1) > div.div-1 > button')
            try:
                await page.waitForSelector(selector='#__next > div > div:nth-child(1) > div.div-2 > div > div.ant-card-body', options={'timeout': 2000})
            except TimeoutError:
                continue
            element = await page.querySelector('#__next > div > div:nth-child(1) > div.div-2 > div > div.ant-card-body')
            result = await page.evaluate('(element) => element.textContent', element)
            chaizi = result.split('●')[1].split('：')[1].split('\u3000')
            line = char + '\t' + ' '.join(chaizi)
            print(line)
            await f.write(line + '\n')
            await page.reload()
            await asyncio.sleep(1)

    await browser.close()


async def search_jd6(queries):
    options = {
      "executablePath": r"/run/current-system/sw/bin/chromium",
      "headless": False,
      "defaultViewport": {"width": 1920, "height": 1080},
      "autoClose": True,
      "dumpio": True,
      "args": [
          "--no-sandbox",
          "--disable-infobars",
      ]
    }

    browser = await launch(**options)
    page = await browser.newPage()
    await page.goto('https://xkinput.gitee.io/tools/search')
    await asyncio.sleep(10)

    async with aiofiles.open('./dicts/chaizi_jd6.txt', 'w') as f:
        for char in queries:
            input = await page.querySelector('#app > div.main-layout.ivu-layout > div > div.ivu-row-flex.ivu-row-flex-center > div > div > form > div:nth-child(1) > div > div > input')
            await input.press('Backspace')
            await input.type(char)
            await page.click(selector='#app > div.main-layout.ivu-layout > div > div.ivu-row-flex.ivu-row-flex-center > div > div > form > div:nth-child(3) > div > button:nth-child(1)')
            await asyncio.sleep(0.1)
            try:
                await page.waitForSelector(selector='#app > div.main-layout.ivu-layout > div > div.ivu-card.ivu-card-bordered > div > div > div > div > div.ivu-table-body > table > tbody > tr:nth-child(1) > td:nth-child(5) > div', options={'timeout': 1000})
            except TimeoutError:
                continue
            element = await page.querySelector('#app > div.main-layout.ivu-layout > div > div.ivu-card.ivu-card-bordered > div > div > div > div > div.ivu-table-body > table > tbody > tr:nth-child(1) > td:nth-child(5) > div')
            result = await page.evaluate('(element) => element.textContent', element)
            chaizi = result.strip()
            line = char + '\t' + chaizi
            print(line)
            await f.write(line + '\n')
            await asyncio.sleep(1)

    await browser.close()


if __name__ == '__main__':
    standard = set()
    standard_list = []

    with open('dicts/8105.dict.yaml') as f:
        for line in f:
            line = line.rstrip()
            if re.match(r'^.\t\w+\t\d+$', line):
                char, _, freq = line.split()
                if char not in standard:
                    standard_list.append(char)
                standard.add(char)
    
    assert len(standard_list) == len(standard)
    asyncio.run(search_jd6(standard_list))

