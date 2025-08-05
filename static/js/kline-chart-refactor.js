/**
 * K线图重构模块
 * 使用ECharts绘制标准的K线图，支持技术指标和实时数据
 */

class KlineChartManager {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.chart = null;
        this.options = {
            showVolume: true,
            showMACD: true,
            showBOLL: true,
            showKDJ: false,
            showRSI: false,
            theme: 'light',
            ...options
        };
        this.klineData = [];
        this.currentSymbol = null;
        
        this.init();
    }
    
    init() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`容器 ${this.containerId} 不存在`);
            return;
        }
        
        // 初始化ECharts实例
        this.chart = echarts.init(container, this.options.theme);
        
        // 设置默认配置
        this.setDefaultOption();
        
        // 绑定窗口大小变化事件
        window.addEventListener('resize', () => {
            this.chart.resize();
        });
    }
    
    setDefaultOption() {
        const option = {
            animation: false,
            legend: {
                bottom: 10,
                left: 'center',
                data: ['K线', 'MA5', 'MA10', 'MA20', 'MA30', 'EMA15']
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: {
                    type: 'cross'
                },
                backgroundColor: 'rgba(245, 245, 245, 0.8)',
                borderWidth: 1,
                borderColor: '#ccc',
                padding: 10,
                textStyle: {
                    color: '#000'
                },
                formatter: (params) => this.formatTooltip(params)
            },
            axisPointer: {
                link: {xAxisIndex: 'all'},
                label: {
                    backgroundColor: '#777'
                }
            },
            toolbox: {
                feature: {
                    dataZoom: {
                        yAxisIndex: false
                    },
                    brush: {
                        type: ['lineX', 'clear']
                    }
                }
            },
            brush: {
                xAxisIndex: 'all',
                brushLink: 'all',
                outOfBrush: {
                    colorAlpha: 0.1
                }
            },
            grid: [
                {
                    left: '10%',
                    right: '8%',
                    height: '50%'
                },
                {
                    left: '10%',
                    right: '8%',
                    top: '63%',
                    height: '16%'
                }
            ],
            xAxis: [
                {
                    type: 'category',
                    data: [],
                    scale: true,
                    boundaryGap: false,
                    axisLine: {onZero: false},
                    splitLine: {show: false},
                    splitNumber: 20,
                    min: 'dataMin',
                    max: 'dataMax',
                    axisPointer: {
                        z: 100
                    }
                },
                {
                    type: 'category',
                    gridIndex: 1,
                    data: [],
                    scale: true,
                    boundaryGap: false,
                    axisLine: {onZero: false},
                    axisTick: {show: false},
                    splitLine: {show: false},
                    axisLabel: {show: false},
                    splitNumber: 20,
                    min: 'dataMin',
                    max: 'dataMax'
                }
            ],
            yAxis: [
                {
                    scale: true,
                    splitArea: {
                        show: true
                    }
                },
                {
                    scale: true,
                    gridIndex: 1,
                    splitNumber: 2,
                    axisLabel: {show: false},
                    axisLine: {show: false},
                    axisTick: {show: false},
                    splitLine: {show: false}
                }
            ],
            dataZoom: [
                {
                    type: 'inside',
                    xAxisIndex: [0, 1],
                    start: 50,
                    end: 100
                },
                {
                    show: true,
                    xAxisIndex: [0, 1],
                    type: 'slider',
                    top: '85%',
                    start: 50,
                    end: 100
                }
            ],
            series: []
        };
        
        this.chart.setOption(option);
    }
    
    /**
     * 更新K线数据
     * @param {Array} klineData - K线数据数组
     * @param {string} symbol - 股票代码
     */
    updateKlineData(klineData, symbol) {
        if (!klineData || klineData.length === 0) {
            console.warn('K线数据为空');
            return;
        }
        
        this.klineData = klineData;
        this.rawKlineData = klineData; // 存储原始数据供tooltip使用
        this.currentSymbol = symbol;
        
        // 处理数据
        const processedData = this.processKlineData(klineData);
        
        // 更新图表
        this.updateChart(processedData);
    }
    
    processKlineData(rawData) {
        const dates = [];
        const klineValues = [];
        const volumes = [];
        const ma5Data = [];
        const ma10Data = [];
        const ma20Data = [];
        const ma30Data = [];
        const bollUpper = [];
        const bollMid = [];
        const bollLower = [];
        const macdDif = [];
        const macdDea = [];
        const macdHistogram = [];
        const ema15Data = [];
        
        // 计算移动平均线
        const calculateMA = (data, period) => {
            const result = [];
            for (let i = 0; i < data.length; i++) {
                if (i < period - 1) {
                    result.push('-');
                } else {
                    let sum = 0;
                    for (let j = 0; j < period; j++) {
                        sum += data[i - j].close;
                    }
                    result.push((sum / period).toFixed(2));
                }
            }
            return result;
        };
        
        // 处理每条数据
        rawData.forEach((item, index) => {
            dates.push(item.trade_date || item.date);
            // 数据格式: [open, close, low, high]
            klineValues.push([
                parseFloat(item.open),
                parseFloat(item.close),
                parseFloat(item.low),
                parseFloat(item.high)
            ]);
            // 成交量数据：只存储成交量值和涨跌标识，不存储序列号
            volumes.push([
                parseFloat(item.vol || item.volume || 0),
                parseFloat(item.close) > parseFloat(item.open) ? 1 : -1
            ]);
            
            // BOLL指标
            if (item.boll_upper !== undefined) {
                bollUpper.push(parseFloat(item.boll_upper) || '-');
                bollMid.push(parseFloat(item.boll_mid) || '-');
                bollLower.push(parseFloat(item.boll_lower) || '-');
            }
            
            // MACD指标
            if (item.macd_dif !== undefined) {
                macdDif.push(parseFloat(item.macd_dif) || 0);
                macdDea.push(parseFloat(item.macd_dea) || 0);
                macdHistogram.push(parseFloat(item.macd_histogram) || 0);
            }
            
            // EMA15指标
            if (item.ema15 !== undefined) {
                ema15Data.push(parseFloat(item.ema15) || '-');
            } else {
                ema15Data.push('-');
            }
        });
        
        // 计算移动平均线
        const ma5 = calculateMA(rawData, 5);
        const ma10 = calculateMA(rawData, 10);
        const ma20 = calculateMA(rawData, 20);
        const ma30 = calculateMA(rawData, 30);
        
        return {
            dates,
            klineValues,
            volumes,
            ma5,
            ma10,
            ma20,
            ma30,
            bollUpper,
            bollMid,
            bollLower,
            macdDif,
            macdDea,
            macdHistogram,
            ema15Data
        };
    }
    
    updateChart(data) {
        const series = [
            // K线图
            {
                name: 'K线',
                type: 'candlestick',
                data: data.klineValues,
                itemStyle: {
                    color: '#ec0000',
                    color0: '#00da3c',
                    borderColor: '#8A0000',
                    borderColor0: '#008F28'
                },
                markPoint: {
                    label: {
                        formatter: function (param) {
                            return param != null ? Math.round(param.value) + '' : '';
                        }
                    },
                    data: [
                        {
                            name: 'Mark',
                            coord: ['2013/5/31', 2300],
                            value: 2300,
                            itemStyle: {
                                color: 'rgb(41,60,85)'
                            }
                        },
                        {
                            name: 'highest value',
                            type: 'max',
                            valueDim: 'highest'
                        },
                        {
                            name: 'lowest value',
                            type: 'min',
                            valueDim: 'lowest'
                        },
                        {
                            name: 'average value on close',
                            type: 'average',
                            valueDim: 'close'
                        }
                    ],
                    tooltip: {
                        formatter: function (param) {
                            return param.name + '<br>' + (param.data.coord || '');
                        }
                    }
                }
            },
            // MA5
            {
                name: 'MA5',
                type: 'line',
                data: data.ma5,
                smooth: true,
                lineStyle: {
                    opacity: 0.5,
                    width: 1
                },
                symbol: 'none'
            },
            // MA10
            {
                name: 'MA10',
                type: 'line',
                data: data.ma10,
                smooth: true,
                lineStyle: {
                    opacity: 0.5,
                    width: 1
                },
                symbol: 'none'
            },
            // MA20
            {
                name: 'MA20',
                type: 'line',
                data: data.ma20,
                smooth: true,
                lineStyle: {
                    opacity: 0.5,
                    width: 1
                },
                symbol: 'none'
            },
            // MA30
            {
                name: 'MA30',
                type: 'line',
                data: data.ma30,
                smooth: true,
                lineStyle: {
                    opacity: 0.5,
                    width: 1
                },
                symbol: 'none'
            },
            // EMA15
            {
                name: 'EMA15',
                type: 'line',
                data: data.ema15Data,
                smooth: true,
                lineStyle: {
                    opacity: 0.8,
                    width: 2,
                    color: '#000000'  // 黑色线条
                },
                symbol: 'none'
            },
            // 成交量
            {
                name: 'Volume',
                type: 'bar',
                xAxisIndex: 1,
                yAxisIndex: 1,
                data: data.volumes.map(item => item[0]), // 只使用成交量值
                itemStyle: {
                    color: function(params) {
                        return data.volumes[params.dataIndex][1] > 0 ? '#ec0000' : '#00da3c';
                    }
                }
            }
        ];
        
        // 添加BOLL指标
        if (this.options.showBOLL && data.bollUpper.length > 0) {
            series.push(
                {
                    name: 'BOLL上轨',
                    type: 'line',
                    data: data.bollUpper,
                    lineStyle: {
                        opacity: 0.6,
                        width: 1,
                        color: '#ec0000',
                        type: 'solid'
                    },
                    symbol: 'none'
                },
                {
                    name: 'BOLL中轨',
                    type: 'line',
                    data: data.bollMid,
                    lineStyle: {
                        opacity: 0.5,
                        width: 1,
                        color: '#ee6666'
                    },
                    symbol: 'none'
                },
                {
                    name: 'BOLL下轨',
                    type: 'line',
                    data: data.bollLower,
                    lineStyle: {
                        opacity: 0.6,
                        width: 1,
                        color: '#ec0000',
                        type: 'solid'
                    },
                    symbol: 'none'
                }
            );
        }
        
        const option = {
            xAxis: [
                {
                    data: data.dates
                },
                {
                    data: data.dates
                }
            ],
            series: series
        };
        
        this.chart.setOption(option, true);
    }
    
    formatTooltip(params) {
        if (!params || params.length === 0) return '';
        
        // 获取数据索引
        const dataIndex = params[0].dataIndex;
        if (dataIndex === undefined || dataIndex < 0 || dataIndex >= this.rawKlineData.length) {
            return '';
        }
        
        // 直接从原始数据获取K线信息
        const rawItem = this.rawKlineData[dataIndex];
        if (!rawItem) return '';
        
        const date = params[0].axisValue || rawItem.trade_date || rawItem.date;
        const open = parseFloat(rawItem.open);
        const close = parseFloat(rawItem.close);
        const high = parseFloat(rawItem.high);
        const low = parseFloat(rawItem.low);
        const volume = parseFloat(rawItem.vol || rawItem.volume || 0);
        
        // 计算涨跌
        const change = close - open;
        const changePercent = ((change / open) * 100).toFixed(2);
        
        let html = `
            <div style="font-weight: bold; margin-bottom: 8px; color: #333;">${date}</div>
            <div style="margin-bottom: 3px;">开盘: <span style="color: #666; font-weight: bold;">${open.toFixed(2)}</span></div>
            <div style="margin-bottom: 3px;">收盘: <span style="color: ${close > open ? '#ec0000' : '#00da3c'}; font-weight: bold;">${close.toFixed(2)}</span></div>
            <div style="margin-bottom: 3px;">最高: <span style="color: #666; font-weight: bold;">${high.toFixed(2)}</span></div>
            <div style="margin-bottom: 3px;">最低: <span style="color: #666; font-weight: bold;">${low.toFixed(2)}</span></div>
            <div style="margin-bottom: 3px;">涨跌: <span style="color: ${change > 0 ? '#ec0000' : '#00da3c'}; font-weight: bold;">${change > 0 ? '+' : ''}${change.toFixed(2)} (${changePercent}%)</span></div>
            <div style="margin-bottom: 3px;">成交量: <span style="color: #666;">${this.formatVolume(volume)}</span></div>
        `;
        
        // 添加技术指标信息
        const maParams = params.filter(p => p.seriesName.startsWith('MA'));
        if (maParams.length > 0) {
            html += '<div style="margin-top: 8px; border-top: 1px solid #ddd; padding-top: 5px;">';
            maParams.forEach(param => {
                if (param.data !== '-' && param.data !== null && param.data !== undefined) {
                    html += `<div style="margin-bottom: 2px;">${param.seriesName}: <span style="color: ${param.color}; font-weight: bold;">${parseFloat(param.data).toFixed(2)}</span></div>`;
                }
            });
            html += '</div>';
        }
        
        // 添加EMA15指标信息
        if (rawItem.ema15 !== undefined && rawItem.ema15 !== null) {
            html += '<div style="margin-top: 8px; border-top: 1px solid #ddd; padding-top: 5px;">';
            html += `<div style="margin-bottom: 2px;">EMA15: <span style="color: #000000; font-weight: bold;">${parseFloat(rawItem.ema15).toFixed(2)}</span></div>`;
            html += '</div>';
        }
        
        // 添加BOLL指标信息
        if (rawItem.boll_upper !== undefined && rawItem.boll_upper !== null) {
            html += '<div style="margin-top: 8px; border-top: 1px solid #ddd; padding-top: 5px;">';
            html += `<div style="margin-bottom: 2px;">BOLL上轨: <span style="color: #ec0000; font-weight: bold;">${parseFloat(rawItem.boll_upper).toFixed(2)}</span></div>`;
            html += `<div style="margin-bottom: 2px;">BOLL中轨: <span style="color: #ee6666; font-weight: bold;">${parseFloat(rawItem.boll_mid).toFixed(2)}</span></div>`;
            html += `<div style="margin-bottom: 2px;">BOLL下轨: <span style="color: #ec0000; font-weight: bold;">${parseFloat(rawItem.boll_lower).toFixed(2)}</span></div>`;
            html += '</div>';
        }
        
        return html;
    }
    
    formatVolume(volume) {
        if (volume >= 100000000) {
            return (volume / 100000000).toFixed(2) + '亿';
        } else if (volume >= 10000) {
            return (volume / 10000).toFixed(2) + '万';
        } else {
            return volume.toString();
        }
    }
    
    /**
     * 设置图表主题
     * @param {string} theme - 主题名称 'light' 或 'dark'
     */
    setTheme(theme) {
        this.options.theme = theme;
        if (this.chart) {
            this.chart.dispose();
            this.init();
            if (this.klineData.length > 0) {
                this.updateKlineData(this.klineData, this.currentSymbol);
            }
        }
    }
    
    /**
     * 显示/隐藏技术指标
     * @param {string} indicator - 指标名称
     * @param {boolean} show - 是否显示
     */
    toggleIndicator(indicator, show) {
        this.options[`show${indicator}`] = show;
        if (this.klineData.length > 0) {
            this.updateKlineData(this.klineData, this.currentSymbol);
        }
    }
    
    /**
     * 销毁图表
     */
    dispose() {
        if (this.chart) {
            this.chart.dispose();
            this.chart = null;
        }
    }
    
    /**
     * 重新调整图表大小
     */
    resize() {
        if (this.chart) {
            this.chart.resize();
        }
    }
}

// 导出类
if (typeof module !== 'undefined' && module.exports) {
    module.exports = KlineChartManager;
} else if (typeof window !== 'undefined') {
    window.KlineChartManager = KlineChartManager;
}