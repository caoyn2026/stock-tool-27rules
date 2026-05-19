#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
27条铁律选股分析引擎 v3
多数据源自动切换：新浪(主) → 东方财富(备)
自动获取数据 + 自动评分 + 自动判定条件
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time, warnings, socket
warnings.filterwarnings('ignore')

# 设置全局socket超时，防止akshare请求卡死
socket.setdefaulttimeout(30)

# ============ 数据获取模块 ============
class StockDataFetcher:
    def __init__(self, stock_code):
        self.raw_code = ''.join(c for c in stock_code if c.isdigit())
        self.market_prefix = 'sh' if self.raw_code.startswith('6') else 'sz'
        self.basic = {}
        self.kline = None
        self.data_source = '?'
        
    def fetch_all(self):
        """获取全部数据，自动切换数据源"""
        self._fetch_kline()  # K线优先（核心数据）
        self._fetch_basic()  # 基本信息补充
        return self
        
    def _fetch_kline(self):
        """获取K线，多源切换"""
        # 方案1: 新浪源（最稳定）
        try:
            symbol = f"{self.market_prefix}{self.raw_code}"
            df = ak.stock_zh_a_daily(
                symbol=symbol,
                start_date=(datetime.now() - timedelta(days=180)).strftime('%Y%m%d'),
                end_date=datetime.now().strftime('%Y%m%d'),
                adjust="qfq"
            )
            if df is not None and len(df) > 10:
                # 统一列名为中文（与原版兼容）
                df = df.rename(columns={
                    'date': '日期', 'open': '开盘', 'high': '最高', 'low': '最低',
                    'close': '收盘', 'volume': '成交量', 'amount': '成交额',
                    'turnover': '换手率'
                })
                # 确保日期是字符串
                df['日期'] = df['日期'].astype(str)
                df['股票代码'] = self.raw_code
                # 补充涨跌幅和振幅
                if '涨跌幅' not in df.columns:
                    df['涨跌幅'] = df['收盘'].pct_change() * 100
                if '振幅' not in df.columns and '最高' in df.columns and '最低' in df.columns:
                    df['振幅'] = (df['最高'] - df['最低']) / df['收盘'].shift(1) * 100
                self.kline = df
                self.data_source = '新浪'
                return
        except Exception as e:
            pass
        
        # 方案2: 东方财富源（重试3次）
        for attempt in range(2):
            try:
                df = ak.stock_zh_a_hist(
                    symbol=self.raw_code, period="daily",
                    start_date=(datetime.now() - timedelta(days=180)).strftime('%Y%m%d'),
                    end_date=datetime.now().strftime('%Y%m%d'),
                    adjust="qfq"
                )
                if df is not None and len(df) > 10:
                    self.kline = df
                    self.data_source = '东方财富'
                    return
            except:
                if attempt < 2:
                    time.sleep(1)
        
        # 方案3: 尝试更短时间范围
        try:
            symbol = f"{self.market_prefix}{self.raw_code}"
            df = ak.stock_zh_a_daily(
                symbol=symbol,
                start_date=(datetime.now() - timedelta(days=90)).strftime('%Y%m%d'),
                end_date=datetime.now().strftime('%Y%m%d'),
                adjust="qfq"
            )
            if df is not None and len(df) > 5:
                df = df.rename(columns={
                    'date': '日期', 'open': '开盘', 'high': '最高', 'low': '最低',
                    'close': '收盘', 'volume': '成交量', 'amount': '成交额',
                    'turnover': '换手率'
                })
                df['日期'] = df['日期'].astype(str)
                df['股票代码'] = self.raw_code
                if '涨跌幅' not in df.columns:
                    df['涨跌幅'] = df['收盘'].pct_change() * 100
                self.kline = df
                self.data_source = '新浪(短期)'
                return
        except:
            pass
        
        self.kline = None
    
    def _fetch_basic(self, retries=2):
        """获取基本信息（含重试）"""
        for attempt in range(retries + 1):
            try:
                df = ak.stock_individual_info_em(symbol=self.raw_code)
                info = dict(zip(df['item'], df['value']))
                mkt = info.get('总市值', 0)
                mkt_yi = float(mkt) / 1e8 if mkt else 0
                self.basic = {
                    '股票代码': self.raw_code,
                    '股票名称': info.get('股票简称', self.raw_code),
                    '最新价': info.get('最新', '-'),
                    '行业': info.get('行业', '-'),
                    '总市值亿': round(mkt_yi, 1),
                    '总市值': info.get('总市值', '-'),
                    '上市时间': info.get('上市时间', '-'),
                }
                return
            except:
                if attempt < retries:
                    time.sleep(1)
        # 从K线中提取基本信息
        if self.kline is not None and len(self.kline) > 0:
            last = self.kline.iloc[-1]
            self.basic = {
                '股票代码': self.raw_code,
                '股票名称': self.raw_code,
                '最新价': float(last.get('收盘', 0)),
                '行业': '-',
                '总市值亿': 0,
                '数据源': self.data_source,
            }
        else:
            self.basic = {'股票代码': self.raw_code, '股票名称': self.raw_code, '行业': '-'}


# ============ 自动评分模块 ============
class AutoScorer:
    DIM_NAMES = {
        'logic': '逻辑清晰度', 'timing': '时机成熟度', 
        'evidence': '证据充分性', 'certainty': '确定性程度',
        'discipline': '纪律执行力', 'riskReward': '风险回报比',
        'confidence': '战意与信心'
    }
    DIM_PRINCIPLES = {
        'logic': '原则2,3,4,27', 'timing': '原则5,6,11,12',
        'evidence': '原则7,8', 'certainty': '原则23,24',
        'discipline': '原则18,19', 'riskReward': '原则10,14,15',
        'confidence': '原则1,16,26'
    }
    
    def __init__(self, fetcher):
        self.f = fetcher
        self.k = fetcher.kline
        self.b = fetcher.basic
        self.result = {
            'scores': {}, 'checks': {}, 'details': {},
            'warnings': [], 'basic': self.b,
            'dataSource': fetcher.data_source,
        }
        self._precalc()
    
    def _to_float(self, series):
        """安全转换为float"""
        return pd.to_numeric(series, errors='coerce').fillna(0)
    
    def _precalc(self):
        if self.k is None or len(self.k) < 10:
            self.cur = 0
            self.ma5 = self.ma10 = self.ma20 = self.ma60 = 0
            self.changes = pd.Series(dtype=float)
            self.recent_low20 = self.recent_high20 = 0
            self.recent_low60 = self.recent_high60 = 0
            return
        
        closes = self._to_float(self.k['收盘'])
        self.cur = float(closes.iloc[-1])
        self.ma5 = float(closes.rolling(5, min_periods=1).mean().iloc[-1])
        self.ma10 = float(closes.rolling(10, min_periods=1).mean().iloc[-1])
        self.ma20 = float(closes.rolling(20, min_periods=1).mean().iloc[-1])
        self.ma60 = float(closes.rolling(60, min_periods=1).mean().iloc[-1]) if len(closes) >= 30 else self.ma20
        self.changes = closes.pct_change().dropna()
        
        lows = self._to_float(self.k['最低'])
        highs = self._to_float(self.k['最高'])
        self.recent_low20 = float(lows.tail(20).min())
        self.recent_high20 = float(highs.tail(20).max())
        self.recent_low60 = float(lows.tail(60).min()) if len(lows) >= 30 else self.recent_low20
        self.recent_high60 = float(highs.tail(60).max()) if len(highs) >= 30 else self.recent_high20
    
    def score(self):
        if not self.cur:
            self.result['error'] = 'K线数据不足，无法分析。可能是网络问题，请稍后重试。'
            return self.result
        self._score_logic()
        self._score_timing()
        self._score_evidence()
        self._score_certainty()
        self._score_discipline()
        self._score_risk_reward()
        self._score_confidence()
        self._calc_position()
        try:
            self._add_market_data()
        except Exception as e:
            self.result['market'] = {'error': str(e)}
            self.result['kline'] = []
        return self.result
    
    # ─── 第1维：逻辑清晰度（原则2,3,4,27）───
    def _score_logic(self):
        s = 4; details = []; checks = {}
        
        if self.cur > self.ma5 > self.ma10 > self.ma20:
            s += 3; details.append("✅ 均线多头排列(MA5>MA10>MA20)，趋势逻辑清晰")
            checks['趋势逻辑清晰'] = True
        elif self.cur > self.ma5 and self.cur > self.ma10:
            s += 1; details.append("⚠️ 短期均线向上，中期偏强")
            checks['趋势逻辑清晰'] = True
        else:
            details.append("❌ 均线混乱，趋势不明确")
            checks['趋势逻辑清晰'] = False
        
        vols = self._to_float(self.k['成交量'])
        cur_vol = float(vols.iloc[-1])
        avg_vol = float(vols.tail(20).mean())
        if avg_vol > 0 and cur_vol > avg_vol * 1.2:
            s += 2; details.append(f"✅ 放量确认(今日量/均量={cur_vol/avg_vol:.1f}x)")
            checks['量价配合'] = True
        else:
            details.append("⚠️ 成交量未放大，量价背离风险")
            checks['量价配合'] = False
        
        if len(self.changes) >= 5:
            up = int((self.changes.tail(5) > 0).sum())
            if up >= 4:
                s += 1; details.append("✅ 近5日方向一致向上")
                checks['方向一致'] = True
            elif up >= 3:
                details.append("⚠️ 近5日方向大致向上")
                checks['方向一致'] = True
            else:
                details.append("❌ 近5日方向不一致")
                checks['方向一致'] = False
        
        self.result['scores']['logic'] = min(s, 10)
        self.result['details']['logic'] = details
        self.result['checks']['logic'] = checks
    
    # ─── 第2维：时机成熟度（原则5,6,11,12）───
    def _score_timing(self):
        s = 4; details = []; checks = {}
        
        drawdown = (self.recent_high60 - self.cur) / self.recent_high60 * 100 if self.recent_high60 > 0 else 0
        if 10 <= drawdown <= 30:
            s += 3; details.append(f"✅ 已从高点调整{drawdown:.1f}%，时机成熟")
            checks['充分调整'] = True
        elif drawdown > 30:
            s += 1; details.append(f"⚠️ 调整{drawdown:.1f}%偏深，可能超跌")
            checks['充分调整'] = True
        elif drawdown > 5:
            details.append(f"⚠️ 仅调整{drawdown:.1f}%，不够充分")
            checks['充分调整'] = False
        else:
            details.append(f"❌ 几乎未调整({drawdown:.1f}%)，追高风险")
            checks['充分调整'] = False
        
        if self.cur > self.ma20 > self.ma60:
            s += 3; details.append("✅ 突破MA20且MA20>MA60，趋势启动")
            checks['均线突破'] = True
        elif self.cur > self.ma20:
            s += 1; details.append("⚠️ 突破MA20，但MA20<MA60，待确认")
            checks['均线突破'] = True
        else:
            details.append("❌ 价格在MA20下方，时机未到")
            checks['均线突破'] = False
        
        closes = self._to_float(self.k['收盘'])
        if len(closes) >= 30:
            std20 = float(closes.tail(20).std())
            std5 = float(closes.tail(5).std())
            if std20 > 0 and std5 < std20 * 0.6:
                s += 2; details.append("✅ 波动收窄，蓄势待发")
                checks['蓄势充分'] = True
            else:
                details.append("⚠️ 波动未收窄")
                checks['蓄势充分'] = False
        
        self.result['scores']['timing'] = min(s, 10)
        self.result['details']['timing'] = details
        self.result['checks']['timing'] = checks
    
    # ─── 第3维：证据充分性（原则7,8）───
    def _score_evidence(self):
        s = 3; details = []; checks = {}
        
        mkt = self.b.get('总市值亿', 0)
        if isinstance(mkt, (int, float)) and mkt > 500:
            s += 2; details.append(f"✅ 总市值{mkt:.0f}亿，大中盘股")
            checks['市值规模'] = True
        elif isinstance(mkt, (int, float)) and mkt > 100:
            s += 1; details.append(f"⚠️ 总市值{mkt:.0f}亿，中盘股")
            checks['市值规模'] = True
        elif isinstance(mkt, (int, float)) and mkt > 0:
            details.append(f"⚠️ 总市值仅{mkt:.0f}亿，小盘股风险大")
            checks['市值规模'] = False
        else:
            details.append("⚠️ 市值数据缺失")
            checks['市值规模'] = True
        
        if self.k is not None and len(self.k) >= 60:
            s += 2; details.append(f"✅ K线数据{len(self.k)}天，技术面充分")
            checks['数据充分'] = True
        elif self.k is not None and len(self.k) >= 20:
            s += 1; details.append(f"⚠️ K线数据{len(self.k)}天，分析有限")
            checks['数据充分'] = True
        else:
            details.append("❌ K线数据不足")
            checks['数据充分'] = False
        
        industry = self.b.get('行业', '-')
        if industry and industry != '-':
            s += 1; details.append(f"✅ 行业：{industry}")
            checks['行业明确'] = True
        else:
            details.append("⚠️ 行业信息缺失")
            checks['行业明确'] = True
        
        if '成交额' in self.k.columns:
            avg_amt = float(self._to_float(self.k['成交额']).tail(20).mean())
            if avg_amt > 1e9:
                s += 2; details.append(f"✅ 日均成交{avg_amt/1e8:.1f}亿，流动性充足")
                checks['流动性充足'] = True
            elif avg_amt > 5e8:
                s += 1; details.append(f"⚠️ 日均成交{avg_amt/1e8:.1f}亿")
                checks['流动性充足'] = True
            elif avg_amt > 0:
                details.append(f"❌ 日均成交{avg_amt/1e8:.1f}亿，流动性差")
                checks['流动性充足'] = False
        
        self.result['scores']['evidence'] = min(s, 10)
        self.result['details']['evidence'] = details
        self.result['checks']['evidence'] = checks
    
    # ─── 第4维：确定性程度（原则23,24）───
    def _score_certainty(self):
        s = 4; details = []; checks = {}
        
        if len(self.changes) >= 20:
            last20 = self.changes.tail(20)
            up = int((last20 > 0).sum())
            down = 20 - up
            if up >= 15:
                s += 3; details.append(f"✅ 近20日{up}涨{down}跌，趋势极强")
                checks['趋势连续'] = True
            elif up >= 12:
                s += 2; details.append(f"✅ 近20日{up}涨{down}跌，趋势较强")
                checks['趋势连续'] = True
            elif up >= 10:
                s += 1; details.append(f"⚠️ 近20日{up}涨{down}跌，趋势一般")
                checks['趋势连续'] = True
            else:
                details.append(f"❌ 近20日仅{up}涨{down}跌，趋势不明")
                checks['趋势连续'] = False
            
            vol_annual = float(last20.std()) * np.sqrt(252) * 100
            if vol_annual < 25:
                s += 2; details.append(f"✅ 年化波动率{vol_annual:.1f}%，稳健")
                checks['波动可控'] = True
            elif vol_annual < 40:
                s += 1; details.append(f"⚠️ 年化波动率{vol_annual:.1f}%")
                checks['波动可控'] = True
            else:
                details.append(f"❌ 波动率{vol_annual:.1f}%，过大")
                checks['波动可控'] = False
        
        if self.recent_low20 > 0:
            above = (self.cur - self.recent_low20) / self.recent_low20 * 100
            if above > 5:
                s += 1; details.append(f"✅ 高于低点{above:.1f}%，支撑明确")
                checks['支撑明确'] = True
            else:
                details.append(f"⚠️ 仅高于低点{above:.1f}%，支撑脆弱")
                checks['支撑明确'] = False
        
        self.result['scores']['certainty'] = min(s, 10)
        self.result['details']['certainty'] = details
        self.result['checks']['certainty'] = checks
    
    # ─── 第5维：纪律执行力（原则18,19）───
    def _score_discipline(self):
        s = 4; details = []; checks = {}
        
        if self.recent_low20 > 0 and self.cur > 0:
            stop_pct = (self.cur - self.recent_low20) / self.cur * 100
            if 5 <= stop_pct <= 15:
                s += 3; details.append(f"✅ 止损幅度{stop_pct:.1f}%，可执行")
                checks['止损明确'] = True
            elif stop_pct < 3:
                details.append(f"❌ 止损幅度仅{stop_pct:.1f}%，极易震出")
                checks['止损明确'] = False
            elif stop_pct < 5:
                s += 1; details.append(f"⚠️ 止损幅度{stop_pct:.1f}%，偏小")
                checks['止损明确'] = True
            else:
                s += 1; details.append(f"⚠️ 止损幅度{stop_pct:.1f}%，较大")
                checks['止损明确'] = True
            
            target_pct = (self.recent_high60 - self.cur) / self.cur * 100 if self.cur > 0 else 0
            rr = target_pct / stop_pct if stop_pct > 0 else 0
            if rr >= 2.5:
                s += 3; details.append(f"✅ 盈亏比{rr:.1f}:1")
                checks['盈亏比合理'] = True
            elif rr >= 1.5:
                s += 1; details.append(f"⚠️ 盈亏比{rr:.1f}:1")
                checks['盈亏比合理'] = True
            else:
                details.append(f"❌ 盈亏比{rr:.1f}:1，不值得")
                checks['盈亏比合理'] = False
        
        self.result['scores']['discipline'] = min(s, 10)
        self.result['details']['discipline'] = details
        self.result['checks']['discipline'] = checks
    
    # ─── 第6维：风险回报比（原则10,14,15）───
    def _score_risk_reward(self):
        s = 4; details = []; checks = {}
        
        if self.recent_low20 > 0 and self.cur > 0:
            risk = self.cur - self.recent_low20
            reward = self.recent_high60 - self.cur
            rr = reward / risk if risk > 0 else 0
            
            if rr >= 3:
                s += 4; details.append(f"✅ 盈亏比{rr:.1f}:1（上方{reward:.2f}/下方{risk:.2f}）")
                checks['高盈亏比'] = True
            elif rr >= 2:
                s += 2; details.append(f"✅ 盈亏比{rr:.1f}:1，可接受")
                checks['高盈亏比'] = True
            elif rr >= 1.5:
                s += 1; details.append(f"⚠️ 盈亏比{rr:.1f}:1，偏低")
                checks['高盈亏比'] = True
            else:
                details.append(f"❌ 盈亏比{rr:.1f}:1，不值得")
                checks['高盈亏比'] = False
            
            max_dd = (self.recent_high60 - self.recent_low60) / self.recent_high60 * 100 if self.recent_high60 > 0 else 0
            if max_dd < 20:
                s += 2; details.append(f"✅ 最大回撤{max_dd:.1f}%，可控")
                checks['回撤可控'] = True
            elif max_dd < 35:
                s += 1; details.append(f"⚠️ 最大回撤{max_dd:.1f}%")
                checks['回撤可控'] = True
            else:
                details.append(f"❌ 最大回撤{max_dd:.1f}%，过大")
                checks['回撤可控'] = False
        
        self.result['scores']['riskReward'] = min(s, 10)
        self.result['details']['riskReward'] = details
        self.result['checks']['riskReward'] = checks
    
    # ─── 第7维：战意与信心（原则1,16,26）───
    def _score_confidence(self):
        s = 4; details = []; checks = {}
        
        if len(self.changes) >= 5:
            last5 = float(self.changes.tail(5).sum() * 100)
            if 0 < last5 < 8:
                s += 2; details.append(f"✅ 近5日涨{last5:.1f}%，稳步上行")
                checks['非追高'] = True
            elif last5 >= 8:
                details.append(f"⚠️ 近5日涨{last5:.1f}%，短期涨幅过大")
                checks['非追高'] = False
            elif -5 < last5 <= 0:
                s += 1; details.append(f"✅ 近5日微跌{last5:.1f}%，可能低吸")
                checks['非追高'] = True
            else:
                details.append(f"❌ 近5日跌{last5:.1f}%，弱势")
                checks['非追高'] = False
        
        if '换手率' in self.k.columns:
            turnover = float(self._to_float(self.k['换手率']).tail(5).mean())
            if 0.5 < turnover < 10:
                s += 2; details.append(f"✅ 换手率{turnover:.2f}%，健康")
                checks['活跃度健康'] = True
            elif turnover >= 10:
                details.append(f"⚠️ 换手率{turnover:.2f}%，过热")
                checks['活跃度健康'] = False
            elif turnover > 0:
                details.append(f"⚠️ 换手率{turnover:.2f}%，清淡")
                checks['活跃度健康'] = False
            else:
                checks['活跃度健康'] = True
        
        vols = self._to_float(self.k['成交量'])
        if len(vols) >= 10:
            v5 = float(vols.tail(5).mean())
            v20 = float(vols.tail(20).mean())
            if v20 > 0:
                ratio = v5 / v20
                if ratio > 1.3:
                    s += 1; details.append(f"✅ 量比={ratio:.1f}，资金介入")
                    checks['资金介入'] = True
                elif ratio > 0.8:
                    details.append(f"⚠️ 量比={ratio:.1f}，平稳")
                    checks['资金介入'] = False
                else:
                    details.append(f"❌ 量比={ratio:.1f}，量能萎缩")
                    checks['资金介入'] = False
        
        self.result['scores']['confidence'] = min(s, 10)
        self.result['details']['confidence'] = details
        self.result['checks']['confidence'] = checks
    
    # ─── 综合决策 ───
    def _calc_position(self):
        scores = self.result['scores']
        weights = {'logic':1.5, 'timing':1.0, 'evidence':1.2, 
                   'certainty':1.5, 'discipline':1.0, 'riskReward':1.3, 'confidence':1.0}
        total = sum(scores[k]*weights[k] for k in scores) / sum(weights.values())
        total = round(total, 1)
        
        if total >= 9:
            position, action, level = '100%', '重仓买入', '极强'
        elif total >= 8:
            position, action, level = '80%', '积极买入', '很强'
        elif total >= 7:
            position, action, level = '60%', '适度买入', '较强'
        elif total >= 6:
            position, action, level = '40%', '轻仓试探', '中等'
        elif total >= 5:
            position, action, level = '20%', '极轻仓', '较弱'
        else:
            position, action, level = '0%', '不建议买入', '放弃'
        
        min_score = min(scores.values())
        min_dim = min(scores, key=scores.get)
        if min_score < 4:
            action += f' ⚠️{self.DIM_NAMES[min_dim]}仅{min_score}分，降级！'
        
        self.result['totalScore'] = total
        self.result['position'] = position
        self.result['action'] = action
        self.result['confidenceLevel'] = level
        self.result['minScore'] = min_score
        self.result['minDim'] = self.DIM_NAMES[min_dim]
        
        stop_price = self.recent_low20 * 0.97
        self.result['buySuggest'] = f"分批买入：{self.recent_low20:.2f}~{self.cur:.2f}"
        self.result['stopLoss'] = f"止损位：{stop_price:.2f}（跌破低点-3%）"
        self.result['targetPrice'] = f"目标位：{self.recent_high60:.2f}（近期高点）"

    # ─── 盘口数据与K线 ───
    def _add_market_data(self):
        """添加实时盘口数据供前端展示"""
        if self.k is None or len(self.k) < 2:
            self.result['market'] = {}
            self.result['kline'] = []
            return
        
        last = self.k.iloc[-1]
        prev = self.k.iloc[-2]
        last_close = self.cur
        prev_close = float(prev['收盘']) if not isinstance(prev['收盘'], pd.Series) else float(self._to_float(prev['收盘']))
        change_pct = (last_close - prev_close) / prev_close * 100 if prev_close > 0 else 0
        
        self.result['market'] = {
            'price': round(last_close, 2),
            'change': round(last_close - prev_close, 2),
            'changePct': round(change_pct, 2),
            'open': round(float(last.get('开盘', 0)), 2),
            'high': round(float(last.get('最高', 0)), 2),
            'low': round(float(last.get('最低', 0)), 2),
            'volume': int(float(last.get('成交量', 0))),
            'amount': float(last.get('成交额', 0)),
            'turnover': round(float(last.get('换手率', 0)), 2) if last.get('换手率', 0) else 0,
            'ma5': round(self.ma5, 2),
            'ma10': round(self.ma10, 2),
            'ma20': round(self.ma20, 2),
            'ma60': round(self.ma60, 2),
        }
        
        # K线数据（最近60天，供前端图表）
        kline_data = []
        n = min(60, len(self.k))
        for i in range(-n, 0):
            row = self.k.iloc[i]
            kline_data.append({
                'date': str(row.get('日期', '')),
                'open': round(float(row.get('开盘', 0)), 2),
                'high': round(float(row.get('最高', 0)), 2),
                'low': round(float(row.get('最低', 0)), 2),
                'close': round(float(row.get('收盘', 0)), 2),
                'volume': int(float(row.get('成交量', 0))),
            })
        self.result['kline'] = kline_data
        
        # 更新basic中的涨跌幅
        self.result['basic']['涨跌幅'] = round(change_pct, 2)


# ============ 命令行测试 ============
if __name__ == '__main__':
    code = input('输入股票代码：').strip()
    print(f'\n⏳ 分析 {code}（自动切换数据源）...\n')
    fetcher = StockDataFetcher(code).fetch_all()
    print(f'数据源: {fetcher.data_source}')
    scorer = AutoScorer(fetcher)
    result = scorer.score()
    
    if 'error' in result:
        print(f"❌ {result['error']}")
    else:
        print(f"{'='*50}")
        print(f"  {result['basic'].get('股票名称','-')} ({code}) [{result['dataSource']}]")
        print(f"  评分：{result['totalScore']} | 仓位：{result['position']} | {result['action']}")
        print(f"{'='*50}")
        for dim in AutoScorer.DIM_NAMES:
            print(f"\n【{AutoScorer.DIM_NAMES[dim]}】{result['scores'][dim]}/10")
            for d in result['details'][dim]:
                print(f"  {d}")
            checks = result['checks'][dim]
            print("  判定：" + "  ".join(f"{'✅' if v else '❌'}{k}" for k,v in checks.items()))
# build: force rebuild 1779172892
