/**
 * 股票数据处理工具函数
 * 用于处理K线数据、除权除息计算等
 */

// 数据配置常量
const STOCK_CONFIG = {
    // K线数据格式: [open, close, low, high]
    KLINE_FORMAT: {
        OPEN: 0,
        CLOSE: 1, 
        LOW: 2,
        HIGH: 3
    },
    // 价格精度
    PRICE_PRECISION: 2,
    // 货币符号
    CURRENCY_SYMBOL: '¥',
    // 百分比精度
    PERCENT_PRECISION: 2
};

/**
 * 安全解析浮点数
 * @param {*} value - 要解析的值
 * @param {number} defaultValue - 默认值
 * @returns {number} 解析后的数值
 */
function safeParseFloat(value, defaultValue = 0) {
    const parsed = parseFloat(value);
    return isNaN(parsed) ? defaultValue : parsed;
}

/**
 * 格式化价格显示
 * @param {number} price - 价格
 * @param {boolean} showCurrency - 是否显示货币符号
 * @param {boolean} isAdjusted - 是否为除权价格
 * @returns {string} 格式化后的价格字符串
 */
function formatPrice(price, showCurrency = true, isAdjusted = false) {
    const formattedPrice = price.toFixed(STOCK_CONFIG.PRICE_PRECISION);
    const currencyPrefix = showCurrency ? STOCK_CONFIG.CURRENCY_SYMBOL : '';
    const adjustedSuffix = isAdjusted ? ' (除权)' : ' (未除权)';
    
    return `${currencyPrefix}${formattedPrice}${adjustedSuffix}`;
}

/**
 * 格式化百分比
 * @param {number} value - 数值
 * @returns {string} 格式化后的百分比字符串
 */
function formatPercent(value) {
    return `${value.toFixed(STOCK_CONFIG.PERCENT_PRECISION)}%`;
}

/**
 * 构建K线数据
 * @param {Array} rawData - 原始数据数组
 * @returns {Array} 格式化的K线数据
 */
function buildCandlestickData(rawData) {
    return rawData.map(item => [
        safeParseFloat(item.open),    // 开盘价
        safeParseFloat(item.close),   // 收盘价
        safeParseFloat(item.low),     // 最低价
        safeParseFloat(item.high)     // 最高价
    ]);
}

/**
 * 计算涨跌幅
 * @param {number} current - 当前价格
 * @param {number} previous - 前一价格
 * @returns {number} 涨跌幅百分比
 */
function calculateChangePercent(current, previous) {
    if (previous === 0) return 0;
    return ((current - previous) / previous) * 100;
}

/**
 * 获取K线数据的OHLC值
 * @param {Array} klineData - K线数据数组
 * @param {string} type - 数据类型 ('open', 'close', 'low', 'high')
 * @returns {number} 对应的价格值
 */
function getKlineValue(klineData, type) {
    const index = STOCK_CONFIG.KLINE_FORMAT[type.toUpperCase()];
    return klineData[index] || 0;
}

/**
 * 验证K线数据格式
 * @param {Array} data - K线数据
 * @returns {boolean} 是否为有效格式
 */
function validateKlineData(data) {
    return Array.isArray(data) && 
           data.length === 4 && 
           data.every(value => typeof value === 'number' && !isNaN(value));
}

/**
 * 生成tooltip HTML内容
 * @param {Array} klineData - K线数据
 * @param {Object} options - 选项配置
 * @returns {string} HTML字符串
 */
function generateTooltipHTML(klineData, options = {}) {
    const { showAdjustedNote = true, showCurrency = true } = options;
    
    if (!validateKlineData(klineData)) {
        return '<div style="color: #999;">数据格式错误</div>';
    }
    
    const adjustedNote = showAdjustedNote ? ' <span style="color: #999; font-size: 11px;">(未除权)</span>' : '';
    const currency = showCurrency ? STOCK_CONFIG.CURRENCY_SYMBOL : '';
    
    return `
        <div style="color: #333; margin-bottom: 3px;">开盘: ${currency}${klineData[0].toFixed(STOCK_CONFIG.PRICE_PRECISION)}${adjustedNote}</div>
        <div style="color: #333; margin-bottom: 3px;">收盘: ${currency}${klineData[1].toFixed(STOCK_CONFIG.PRICE_PRECISION)}${adjustedNote}</div>
        <div style="color: #333; margin-bottom: 3px;">最低: ${currency}${klineData[2].toFixed(STOCK_CONFIG.PRICE_PRECISION)}${adjustedNote}</div>
        <div style="color: #333; margin-bottom: 3px;">最高: ${currency}${klineData[3].toFixed(STOCK_CONFIG.PRICE_PRECISION)}${adjustedNote}</div>
    `;
}

// 导出工具函数（如果使用模块化）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        STOCK_CONFIG,
        safeParseFloat,
        formatPrice,
        formatPercent,
        buildCandlestickData,
        calculateChangePercent,
        getKlineValue,
        validateKlineData,
        generateTooltipHTML
    };
}