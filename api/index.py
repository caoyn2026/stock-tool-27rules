#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""27条铁律选股工具 - Vercel Serverless Function 入口"""
import sys, os, json

# 确保能找到同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request, send_from_directory
from analyzer_module import StockDataFetcher, AutoScorer

app = Flask(__name__)

# ============ 股票列表缓存 ============
STOCK_CACHE = []
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_cache.json')

def load_cache():
    global STOCK_CACHE
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            STOCK_CACHE = json.load(f)

def search_stocks(query, limit=10):
    q = query.strip().upper()
    if not q:
        return []
    results = []
    for s in STOCK_CACHE:
        code, name, py = s['c'], s['n'], s['p']
        if code.startswith(q):
            results.append(s)
        elif py.startswith(q):
            results.append(s)
        elif q.lower() in name:
            results.append(s)
        if len(results) >= limit:
            break
    return results

def resolve_code(query):
    q = query.strip()
    digits = ''.join(c for c in q if c.isdigit())
    if len(digits) == 6:
        return digits, None
    matches = search_stocks(q, limit=1)
    if matches:
        return matches[0]['c'], matches[0]['n']
    return None, None

# 启动时加载缓存
load_cache()

# ============ API 路由 ============

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'results': []})
    results = search_stocks(q, limit=15)
    return jsonify({'results': results})

@app.route('/api/analyze')
def api_analyze():
    raw = request.args.get('code', '').strip()
    if not raw:
        return jsonify({'error': '请输入股票代码、拼音缩写或名称'})
    code, matched_name = resolve_code(raw)
    if not code:
        suggestions = search_stocks(raw, limit=5)
        if suggestions:
            sug_text = '、'.join([f'{s["c"]}({s["n"]})' for s in suggestions])
            return jsonify({'error': f'未找到匹配股票，您是否想找：{sug_text}？'})
        return jsonify({'error': f'未找到匹配 "{raw}" 的股票'})
    try:
        fetcher = StockDataFetcher(code).fetch_all()
        scorer = AutoScorer(fetcher)
        result = scorer.score()
        if 'error' in result:
            return jsonify({'error': result['error']})
        if matched_name and result['basic'].get('股票名称', '') in (code, '-', ''):
            result['basic']['股票名称'] = matched_name
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'分析出错: {str(e)}'})

# Vercel需要的WSGI入口
# Vercel Python runtime会自动发现app对象
