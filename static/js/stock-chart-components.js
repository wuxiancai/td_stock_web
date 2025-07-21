/**
 * 股票数据可视化组件库
 * 提供可复用的图表组件和数据处理工具
 */

class StockChartManager {
    constructor() {
        this.charts = new Map();
        this.defaultOptions = {
            responsive: true,
            maintainAspectRatio: false,
            animation: {
                duration: 300
            },
            interaction: {
                intersect: false,
                mode: 'index'
            }
        };
    }

    /**
     * 创建K线图
     */
    createKlineChart(containerId, data, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) {
            throw new Error(`容器 ${containerId} 不存在`);
        }

        const chartOptions = {
            ...this.defaultOptions,
            ...options,
            series: [{
                type: 'candlestick',
                data: this.formatKlineData(data),
                itemStyle: {
                    color: '#ef5350',      // 阳线颜色
                    color0: '#26a69a',     // 阴线颜色
                    borderColor: '#ef5350',
                    borderColor0: '#26a69a'
                }
            }],
            xAxis: {
                type: 'category',
                data: data.map(item => item.trade_date),
                axisLine: { lineStyle: { color: '#8392A5' } }
            },
            yAxis: {
                scale: true,
                axisLine: { lineStyle: { color: '#8392A5' } },
                splitLine: { show: false }
            },
            grid: {
                left: '10%',
                right: '10%',
                bottom: '15%'
            },
            tooltip: {
                trigger: 'axis',
                formatter: this.klineTooltipFormatter
            }
        };

        const chart = echarts.init(container);
        chart.setOption(chartOptions);
        
        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * 创建分时图
     */
    createTimeChart(containerId, data, options = {}) {
        const container = document.getElementById(containerId);
        if (!container) {
            throw new Error(`容器 ${containerId} 不存在`);
        }

        const chartOptions = {
            ...this.defaultOptions,
            ...options,
            series: [{
                type: 'line',
                data: data.map(item => [item.time, item.price]),
                smooth: true,
                lineStyle: {
                    color: '#1976d2',
                    width: 2
                },
                areaStyle: {
                    color: {
                        type: 'linear',
                        x: 0, y: 0, x2: 0, y2: 1,
                        colorStops: [
                            { offset: 0, color: 'rgba(25, 118, 210, 0.3)' },
                            { offset: 1, color: 'rgba(25, 118, 210, 0.05)' }
                        ]
                    }
                }
            }],
            xAxis: {
                type: 'time',
                axisLine: { lineStyle: { color: '#8392A5' } }
            },
            yAxis: {
                type: 'value',
                scale: true,
                axisLine: { lineStyle: { color: '#8392A5' } },
                splitLine: { 
                    lineStyle: { 
                        color: '#E0E6ED',
                        type: 'dashed'
                    }
                }
            },
            tooltip: {
                trigger: 'axis',
                formatter: this.timeTooltipFormatter
            }
        };

        const chart = echarts.init(container);
        chart.setOption(chartOptions);
        
        this.charts.set(containerId, chart);
        return chart;
    }

    /**
     * 格式化K线数据
     */
    formatKlineData(data) {
        return data.map(item => [
            parseFloat(item.open),
            parseFloat(item.close),
            parseFloat(item.low),
            parseFloat(item.high)
        ]);
    }

    /**
     * K线图tooltip格式化
     */
    klineTooltipFormatter(params) {
        const data = params[0];
        const values = data.data;
        
        return `
            <div class="tooltip-container">
                <div class="tooltip-title">${data.name}</div>
                <div class="tooltip-item">
                    <span class="label">开盘:</span>
                    <span class="value">${values[0].toFixed(2)}</span>
                </div>
                <div class="tooltip-item">
                    <span class="label">收盘:</span>
                    <span class="value">${values[1].toFixed(2)}</span>
                </div>
                <div class="tooltip-item">
                    <span class="label">最低:</span>
                    <span class="value">${values[2].toFixed(2)}</span>
                </div>
                <div class="tooltip-item">
                    <span class="label">最高:</span>
                    <span class="value">${values[3].toFixed(2)}</span>
                </div>
            </div>
        `;
    }

    /**
     * 分时图tooltip格式化
     */
    timeTooltipFormatter(params) {
        const data = params[0];
        
        return `
            <div class="tooltip-container">
                <div class="tooltip-title">${data.name}</div>
                <div class="tooltip-item">
                    <span class="label">价格:</span>
                    <span class="value">${data.value[1].toFixed(2)}</span>
                </div>
            </div>
        `;
    }

    /**
     * 更新图表数据
     */
    updateChart(containerId, newData) {
        const chart = this.charts.get(containerId);
        if (!chart) {
            console.warn(`图表 ${containerId} 不存在`);
            return;
        }

        chart.setOption({
            series: [{
                data: newData
            }]
        });
    }

    /**
     * 销毁图表
     */
    destroyChart(containerId) {
        const chart = this.charts.get(containerId);
        if (chart) {
            chart.dispose();
            this.charts.delete(containerId);
        }
    }

    /**
     * 销毁所有图表
     */
    destroyAllCharts() {
        this.charts.forEach((chart, containerId) => {
            chart.dispose();
        });
        this.charts.clear();
    }

    /**
     * 响应式调整
     */
    resizeCharts() {
        this.charts.forEach(chart => {
            chart.resize();
        });
    }
}

class DataProcessor {
    /**
     * 计算技术指标 - 移动平均线
     */
    static calculateMA(data, period) {
        const result = [];
        
        for (let i = 0; i < data.length; i++) {
            if (i < period - 1) {
                result.push(null);
                continue;
            }
            
            let sum = 0;
            for (let j = i - period + 1; j <= i; j++) {
                sum += parseFloat(data[j].close);
            }
            
            result.push((sum / period).toFixed(2));
        }
        
        return result;
    }

    /**
     * 计算技术指标 - RSI
     */
    static calculateRSI(data, period = 14) {
        const gains = [];
        const losses = [];
        
        for (let i = 1; i < data.length; i++) {
            const change = parseFloat(data[i].close) - parseFloat(data[i - 1].close);
            gains.push(change > 0 ? change : 0);
            losses.push(change < 0 ? Math.abs(change) : 0);
        }
        
        const result = [null]; // 第一个值为null
        
        for (let i = period - 1; i < gains.length; i++) {
            let avgGain, avgLoss;
            
            if (i === period - 1) {
                // 第一个RSI值
                avgGain = gains.slice(0, period).reduce((a, b) => a + b) / period;
                avgLoss = losses.slice(0, period).reduce((a, b) => a + b) / period;
            } else {
                // 后续RSI值使用平滑移动平均
                const prevAvgGain = result[i - 1] ? 
                    (result[i - 1].avgGain * (period - 1) + gains[i]) / period : 0;
                const prevAvgLoss = result[i - 1] ? 
                    (result[i - 1].avgLoss * (period - 1) + losses[i]) / period : 0;
                
                avgGain = prevAvgGain;
                avgLoss = prevAvgLoss;
            }
            
            const rs = avgGain / avgLoss;
            const rsi = 100 - (100 / (1 + rs));
            
            result.push({
                rsi: rsi.toFixed(2),
                avgGain,
                avgLoss
            });
        }
        
        return result.map(item => item ? parseFloat(item.rsi) : null);
    }

    /**
     * 数据验证
     */
    static validateStockData(data) {
        if (!Array.isArray(data) || data.length === 0) {
            throw new Error('数据格式错误：应为非空数组');
        }

        const requiredFields = ['open', 'close', 'high', 'low'];
        
        for (let i = 0; i < data.length; i++) {
            const item = data[i];
            
            // 检查必需字段
            for (const field of requiredFields) {
                if (!(field in item) || item[field] === null || item[field] === undefined) {
                    throw new Error(`数据验证失败：第${i}行缺少字段 ${field}`);
                }
            }
            
            // 检查价格逻辑
            const { open, close, high, low } = item;
            if (high < Math.max(open, close, low) || low > Math.min(open, close, high)) {
                console.warn(`数据警告：第${i}行价格逻辑异常`);
            }
        }
        
        return true;
    }
}

class UIComponents {
    /**
     * 创建加载指示器
     */
    static createLoader(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="loader-container">
                <div class="loader">
                    <div class="loader-spinner"></div>
                    <div class="loader-text">数据加载中...</div>
                </div>
            </div>
        `;
    }

    /**
     * 移除加载指示器
     */
    static removeLoader(containerId) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const loader = container.querySelector('.loader-container');
        if (loader) {
            loader.remove();
        }
    }

    /**
     * 显示错误消息
     */
    static showError(containerId, message) {
        const container = document.getElementById(containerId);
        if (!container) return;

        container.innerHTML = `
            <div class="error-container">
                <div class="error-icon">⚠️</div>
                <div class="error-message">${message}</div>
                <button class="retry-button" onclick="location.reload()">重试</button>
            </div>
        `;
    }

    /**
     * 创建数据表格
     */
    static createDataTable(containerId, data, columns) {
        const container = document.getElementById(containerId);
        if (!container) return;

        let tableHTML = '<table class="data-table"><thead><tr>';
        
        // 表头
        columns.forEach(col => {
            tableHTML += `<th>${col.title}</th>`;
        });
        tableHTML += '</tr></thead><tbody>';
        
        // 表体
        data.forEach(row => {
            tableHTML += '<tr>';
            columns.forEach(col => {
                const value = row[col.key];
                const formattedValue = col.formatter ? col.formatter(value) : value;
                tableHTML += `<td>${formattedValue}</td>`;
            });
            tableHTML += '</tr>';
        });
        
        tableHTML += '</tbody></table>';
        container.innerHTML = tableHTML;
    }
}

// 全局实例
const stockChartManager = new StockChartManager();

// 窗口大小改变时调整图表
window.addEventListener('resize', () => {
    stockChartManager.resizeCharts();
});

// 页面卸载时清理图表
window.addEventListener('beforeunload', () => {
    stockChartManager.destroyAllCharts();
});