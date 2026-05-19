import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads")
DATA_DIR = os.path.join(BASE_DIR, "data")

for d in [DOWNLOADS_DIR, DATA_DIR]:
    os.makedirs(d, exist_ok=True)

# 爬取配置
MOVIES_PER_CATEGORY = 10
SCHEDULE_HOUR = 9
SCHEDULE_MINUTE = 0

# 网站配置
SITES = {
    "cnmkv": {
        "name": "中国高清网",
        "base_url": "https://www.cnmkv.com",
        "categories": {
            "oumei": {"name": "欧美电影", "path": "/category/oumeidianying/"},
            "guochan": {"name": "国产电影", "path": "/category/guochandianying/"},
            "rihan": {"name": "日韩电影", "path": "/category/rihandianying/"},
        },
    },
    "hdzu": {
        "name": "高清族",
        "base_url": "https://www.hdzu.cc",
        "categories": {
            "all": {"name": "全部", "path": "/"},
        },
    },
}

# 请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# Excel输出
EXCEL_FILENAME = "movies.xlsx"
EXCEL_PATH = os.path.join(BASE_DIR, EXCEL_FILENAME)

# 去重数据库
DB_PATH = os.path.join(DATA_DIR, "movies.db")
