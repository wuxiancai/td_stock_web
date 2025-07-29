#!/usr/bin/env python3
"""
测试价格修复效果的脚本
"""

import requests
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def test_price_display():
    """测试股票详情页面的价格显示"""
    
    # 配置Chrome选项
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # 无头模式
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    
    try:
        # 启动浏览器
        driver = webdriver.Chrome(options=chrome_options)
        
        # 访问股票详情页面
        url = "http://localhost:8080/stock/300354"
        print(f"访问页面: {url}")
        driver.get(url)
        
        # 等待页面加载完成
        wait = WebDriverWait(driver, 10)
        
        # 等待stockPrice元素出现
        stock_price_element = wait.until(
            EC.presence_of_element_located((By.ID, "stockPrice"))
        )
        
        # 等待一段时间让JavaScript执行
        time.sleep(3)
        
        # 获取价格显示
        price_text = stock_price_element.text
        print(f"红框中显示的价格: {price_text}")
        
        # 检查是否显示了期望的价格
        if "40.65" in price_text:
            print("✅ 修复成功！红框中显示了正确的前一个交易日收盘价 40.65")
            return True
        elif "40.31" in price_text:
            print("❌ 修复失败！红框中仍显示错误的价格 40.31")
            return False
        else:
            print(f"⚠️  红框中显示了其他价格: {price_text}")
            return False
            
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        return False
    finally:
        if 'driver' in locals():
            driver.quit()

def test_api_response():
    """测试API响应"""
    try:
        # 测试每日基础数据API
        response = requests.get("http://localhost:8080/api/stock/300354/daily_basic", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"每日基础数据API响应成功: {data.get('success', False)}")
        else:
            print(f"每日基础数据API响应失败: {response.status_code}")
            
        # 测试实时交易数据API
        response = requests.get("http://localhost:8080/api/stock/realtime_trading_data", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"实时交易数据API响应成功: {data.get('success', False)}")
        else:
            print(f"实时交易数据API响应失败: {response.status_code}")
            
    except Exception as e:
        print(f"API测试失败: {e}")

if __name__ == "__main__":
    print("开始测试价格修复效果...")
    print("=" * 50)
    
    # 测试API
    print("1. 测试API响应...")
    test_api_response()
    print()
    
    # 测试页面显示
    print("2. 测试页面价格显示...")
    success = test_price_display()
    print()
    
    if success:
        print("🎉 测试完成！价格修复成功！")
    else:
        print("❌ 测试完成！价格修复需要进一步调试。")