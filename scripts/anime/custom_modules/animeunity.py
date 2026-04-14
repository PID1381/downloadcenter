#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

BASE_URL = r"https://www.animeunity.so/"
SEARCH_URL = BASE_URL + r"<span data-v-31c42592="" class="livesearch-info info-2"> • 1/1 episodi</span></div></div></a> <!----></div> <!----></div></div>"

SELECTORS = {
    "container": r"<div data-v-31c42592="" class="search-container"><div data-v-31c42592="" class="input-group search-group fade-scale">",
    "item": r"<div data-v-31c42592="" class="result"><a data-v-31c42592="" href="http://www.animeunity.so/anime/2593-maison-ikkoku-cara-dolce-kyoko-ita" class="livesearch-item"><div data-v-31c42592="" class="livesearch-image"><img data-v-31c42592="" src="https://img.animeunity.so/anime/nx1453-mghhMKzxEVcQ.jpg" alt="" height="40" width="40"></div> <div data-v-31c42592="" class="livesearch-name"><div data-v-31c42592="" class="livesearch-title">Maison Ikkoku - Cara dolce Kyoko (ITA)</div> <div data-v-31c42592="" class="livesearch-info-wrap"><span data-v-31c42592="" class="livesearch-info">1986</span> <span data-v-31c42592="" class="livesearch-info info-2">TV</span> <span data-v-31c42592="" class="livesearch-info info-2"> • 96/96 episodi</span></div></div></a> <!----></div>",
    "title": r"<div data-v-31c42592="" class="livesearch-title">Maison Ikkoku - Cara dolce Kyoko (ITA)</div>",
    "link": r"<a data-v-31c42592="" href="http://www.animeunity.so/anime/2593-maison-ikkoku-cara-dolce-kyoko-ita" class="livesearch-item">",
    "link_attr": r"http://www.animeunity.so/anime/2593-maison-ikkoku-cara-dolce-kyoko-ita",
}

def search_custom(query, debug=False):
    try:
        if debug:
            print(f"  [*] Searching {query}...")
        
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        }
        
        params = {r"q": query}
        response = requests.get(SEARCH_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, "html.parser")
        
        container = soup.select_one(SELECTORS["container"])
        if not container:
            return []
        
        results = []
        
        for item in container.select(SELECTORS["item"]):
            try:
                title_elem = item.select_one(SELECTORS["title"])
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                if not title:
                    continue
                
                link_elem = item.select_one(SELECTORS["link"])
                if not link_elem:
                    continue
                
                link = link_elem.get(SELECTORS["link_attr"], "")
                if not link:
                    continue
                
                if not link.startswith("http"):
                    link = urljoin(BASE_URL, link)
                
                results.append({
                    "title": title,
                    "link": link,
                    "raw_title": title,
                })
            
            except Exception:
                continue
        
        return results
    
    except Exception as e:
        print(f"  [ERROR] {e}")
        return []

def test_search(query="naruto"):
    results = search_custom(query, debug=True)
    print()
    if results:
        for i, r in enumerate(results[:3], 1):
            print(f"    {i}. {r['title']}")
    else:
        print("  No results")

if __name__ == "__main__":
    test_search()
