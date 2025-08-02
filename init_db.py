#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库初始化脚本
用于创建必要的数据库表和初始化数据
"""

import os
import sqlite3
from pathlib import Path

def create_database():
    """创建数据库和必要的表"""
    
    # 获取数据库路径
    db_path = os.environ.get('DATABASE_PATH', 'data/stock_data.db')
    
    # 确保数据目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    
    print(f"初始化数据库: {db_path}")
    
    try:
        # 连接数据库（如果不存在会自动创建）
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 创建股票基本信息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_basic (
                ts_code TEXT PRIMARY KEY,
                symbol TEXT,
                name TEXT,
                area TEXT,
                industry TEXT,
                market TEXT,
                list_date TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 创建股票价格数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT,
                trade_date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                pre_close REAL,
                change REAL,
                pct_chg REAL,
                vol REAL,
                amount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        ''')
        
        # 创建九转序列数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nine_turn_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts_code TEXT,
                trade_date TEXT,
                nine_turn_up INTEGER DEFAULT 0,
                nine_turn_down INTEGER DEFAULT 0,
                countdown_up INTEGER DEFAULT 0,
                countdown_down INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(ts_code, trade_date)
            )
        ''')
        
        # 创建用户自选股表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_watchlist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                ts_code TEXT,
                name TEXT,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, ts_code)
            )
        ''')
        
        # 创建系统配置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 插入默认配置
        default_configs = [
            ('last_update_date', '', '最后更新日期'),
            ('cache_enabled', 'true', '是否启用缓存'),
            ('api_rate_limit', '199', 'API请求频率限制'),
            ('system_version', '1.0.0', '系统版本')
        ]
        
        for key, value, desc in default_configs:
            cursor.execute('''
                INSERT OR IGNORE INTO system_config (key, value, description)
                VALUES (?, ?, ?)
            ''', (key, value, desc))
        
        # 提交事务
        conn.commit()
        
        print("数据库初始化完成！")
        print("创建的表:")
        print("- stock_basic: 股票基本信息")
        print("- stock_daily: 股票日线数据")
        print("- nine_turn_data: 九转序列数据")
        print("- user_watchlist: 用户自选股")
        print("- system_config: 系统配置")
        
        return True
        
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        return False
        
    finally:
        if conn:
            conn.close()

def check_database():
    """检查数据库状态"""
    db_path = os.environ.get('DATABASE_PATH', 'data/stock_data.db')
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"数据库文件: {db_path}")
        print(f"现有表: {', '.join(tables)}")
        
        # 检查每个表的记录数
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"- {table}: {count} 条记录")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"检查数据库失败: {e}")
        return False

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'check':
        # 检查数据库状态
        check_database()
    else:
        # 初始化数据库
        success = create_database()
        if success:
            print("\n数据库初始化成功！")
            check_database()
        else:
            print("\n数据库初始化失败！")
            sys.exit(1)