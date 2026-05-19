#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""27条铁律选股工具 - Vercel Serverless Function 入口"""
import sys, os, json

# 确保能找到同目录模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request
from analyzer_module import StockDataFetcher, AutoScorer
from stock_names import STOCK_NAMES

app = Flask(__name__)

# ============ 股票搜索 ============
# 从STOCK_NAMES构建搜索列表（含拼音首字母）
STOCK_LIST = []
try:
    _cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_cache.json')
    if os.path.exists(_cache_path):
        with open(_cache_path, 'r', encoding='utf-8') as f:
            STOCK_LIST = json.load(f)
except:
    pass

# 如果缓存文件不存在，从STOCK_NAMES构建
if not STOCK_LIST:
    STOCK_LIST = [{'c': k, 'n': v, 'p': ''} for k, v in STOCK_NAMES.items()]

def search_stocks(query, limit=10):
    q = query.strip().upper()
    if not q:
        return []
    results = []
    for s in STOCK_LIST:
        code, name, py = s['c'], s['n'], s.get('p', '')
        if code.startswith(q):
            results.append(s)
        elif py and py.startswith(q):
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
        # 纯数字代码，从STOCK_NAMES查找
        return digits, STOCK_NAMES.get(digits)
    matches = search_stocks(q, limit=1)
    if matches:
        return matches[0]['c'], matches[0]['n']
    return None, None

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
        # 用缓存的干净名称覆盖（akshare返回的名称可能有空格或缺失）
        if matched_name:
            result['basic']['股票名称'] = matched_name
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'分析出错: {str(e)}'})

# Vercel需要的WSGI入口
# Vercel Python runtime会自动发现app对象
