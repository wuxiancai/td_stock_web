import json
import requests

try:
    response = requests.get('http://localhost:8080/api/stock/000001/realtime')
    data = response.json()
    
    print('=== 数据结构检查 ===')
    print('spot存在:', bool(data.get('spot')))
    print('money_flow存在:', bool(data.get('money_flow')))
    print('kline_data存在:', bool(data.get('kline_data')))
    print('minute_data存在:', bool(data.get('minute_data')))
    
    if data.get('kline_data'):
        print('K线数据条数:', len(data['kline_data']))
        if len(data['kline_data']) > 0:
            latest = data['kline_data'][-1]
            print('最新K线字段:', list(latest.keys()))
            print('最新K线数据:')
            for k in ['trade_date', 'open', 'high', 'low', 'close', 'vol', 'amount', 'turnover_rate']:
                print(f'  {k}: {latest.get(k, "不存在")}')
                
    if data.get('money_flow'):
        print('\n=== 资金流向数据 ===')
        mf = data['money_flow']
        for k in ['close_price', 'change_percent', 'turnover_rate', 'volume_ratio', 'amount']:
            print(f'  {k}: {mf.get(k, "不存在")}')
            
except Exception as e:
    print(f'错误: {e}')