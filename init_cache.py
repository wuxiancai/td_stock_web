#!/usr/bin/env python3
"""
初始化缓存目录脚本
用于在部署时确保所有必要的缓存目录存在
"""

import os
import sys
from pathlib import Path

def init_cache_directories():
    """初始化缓存目录结构"""
    
    # 获取项目根目录
    project_root = Path(__file__).parent
    cache_dir = project_root / 'cache'
    
    # 创建主缓存目录
    cache_dir.mkdir(exist_ok=True)
    print(f"✓ 创建缓存目录: {cache_dir}")
    
    # 创建intraday子目录
    intraday_dir = cache_dir / 'intraday'
    intraday_dir.mkdir(exist_ok=True)
    print(f"✓ 创建分时图缓存目录: {intraday_dir}")
    
    # 检查权限
    try:
        test_file = cache_dir / 'test_write.tmp'
        test_file.write_text('test')
        test_file.unlink()
        print(f"✓ 缓存目录写入权限正常")
    except Exception as e:
        print(f"✗ 缓存目录写入权限异常: {e}")
        return False
    
    print("缓存目录初始化完成！")
    return True

if __name__ == '__main__':
    success = init_cache_directories()
    sys.exit(0 if success else 1)