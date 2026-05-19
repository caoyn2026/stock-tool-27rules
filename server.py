#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""27条铁律选股工具 - Flask Web服务 v3
支持：股票代码 / 拼音缩写 / 中文名称 搜索
"""
import sys, os, json, re
from flask import Flask, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyzer import StockDataFetcher, AutoScorer

app = Flask(__name__, static_folder='static')

# ============ 股票列表缓存 ============
STOCK_CACHE = []
CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stock_cache.json')

def load_cache():
    global STOCK_CACHE
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            STOCK_CACHE = json.load(f)
        print(f'  股票缓存: {len(STOCK_CACHE)} 只')
    else:
        print('  ⚠️ 无股票缓存，请运行 build_cache.py')

def search_stocks(query, limit=10):
    """搜索股票：支持代码/拼音/名称"""
    q = query.strip().upper()
    if not q:
        return []
    results = []
    for s in STOCK_CACHE:
        code, name, py = s['c'], s['n'], s['p']
        # 代码前缀匹配
        if code.startswith(q):
            results.append(s)
        # 拼音前缀匹配
        elif py.startswith(q):
            results.append(s)
        # 名称包含匹配
        elif q.lower() in name:
            results.append(s)
        if len(results) >= limit:
            break
    return results

def resolve_code(query):
    """将用户输入解析为股票代码
    - 纯6位数字 → 直接作为代码
    - 拼音缩写/名称 → 搜索取第一个
    """
    q = query.strip()
    digits = ''.join(c for c in q if c.isdigit())
    if len(digits) == 6:
        return digits, None
    
    # 非纯数字，走搜索
    matches = search_stocks(q, limit=1)
    if matches:
        return matches[0]['c'], matches[0]['n']
    return None, None

# ============ API ============

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/search')
def api_search():
    """搜索股票（代码/拼音/名称）"""
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'results': []})
    results = search_stocks(q, limit=15)
    return jsonify({'results': results})

@app.route('/api/analyze')
def api_analyze():
    """分析股票（自动解析输入）"""
    raw = request.args.get('code', '').strip()
    if not raw:
        return jsonify({'error': '请输入股票代码、拼音缩写或名称'})
    
    code, matched_name = resolve_code(raw)
    if not code:
        # 没找到，给出建议
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
        # 如果是搜索匹配的，补充名称
        if matched_name and result['basic'].get('股票名称', '') in (code, '-', ''):
            result['basic']['股票名称'] = matched_name
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'分析出错: {str(e)}'})

# 启动时加载缓存
load_cache()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5190))
    print('='*50)
    print('🎯 27条铁律·选股决策系统 v3')
    print('   支持：代码 / 拼音缩写 / 中文名')
    print(f'   浏览器打开: http://127.0.0.1:{port}')
    print('='*50)
    app.run(host='0.0.0.0', port=port, debug=False)
