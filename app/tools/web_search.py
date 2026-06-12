import aiohttp
from app.core.config import settings


class WebSearchTool:
    """网络搜索工具 - 调用SerpAPI获取搜索结果"""

    @staticmethod
    async def search(query: str, num_results: int = 5) -> list[dict]:
        """
        执行搜索并返回结果列表
        每条结果包含 title / snippet / link
        """
        url = "https://serpapi.com/search"
        params = {
            "q": query,
            "api_key": settings.SERPAPI_API_KEY,
            "num": num_results,
            "hl": "zh-cn",  # 中文搜索结果
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as resp:
                data = await resp.json()
                # 提取有机搜索结果
                results = []
                for item in data.get("organic_results", []):
                    results.append({
                        "title": item.get("title"),
                        "snippet": item.get("snippet"),
                        "link": item.get("link"),
                    })
                return results