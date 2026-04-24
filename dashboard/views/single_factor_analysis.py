import os
import yaml
import datetime
import pandas as pd
import numpy as np
import streamlit as st
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Literal, Any
import seaborn as sns
from matplotlib import cm, colors

from pyecharts import options as opts
from pyecharts.charts import Bar, Line, Kline
from streamlit_echarts import st_pyecharts
from pyecharts.commons.utils import JsCode

# Local Module (保留原有引用)
try:
    from src.factor_eval.get_eval import EVALUATION
except ImportError:
    st.error("无法导入本地模块: src.factor_eval.get_eval，请检查路径。")
    # 创建一个 dummy 类防止 IDE 报错，实际运行时会报错停止
    class EVALUATION:
        def __init__(self, *args, **kwargs): pass
        def calc_IC(self, method): return pd.DataFrame()
        def calc_grouped(self, quantile, bins): return pd.DataFrame(), pd.DataFrame()

# ------------------------------------------------------------------------
# Constants & Config
# ------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data" # Path("./data")
RAW_DATA_PATH = DATA_DIR / "raw" / "all_stock_data.parquet"
FACTOR_DIR = DATA_DIR / "factors"
DESC_PATH = DATA_DIR / "factor_desc.yaml"
# print(123, RAW_DATA_PATH, FACTOR_DIR, DESC_PATH)
# st.set_page_config(page_title="单因子分析", layout="wide")

# ------------------------------------------------------------------------
# 1. Data Loader
# ------------------------------------------------------------------------
@st.cache_data
def load_base_data() -> pd.DataFrame:
    """加载基础行情数据"""
    if not RAW_DATA_PATH.exists():
        st.error(f"数据文件不存在: {RAW_DATA_PATH}")
        return pd.DataFrame()
    return pd.read_parquet(RAW_DATA_PATH)

@st.cache_data
def load_factor_data(type_i: str, name: str) -> pd.DataFrame:
    """加载因子数据"""
    path = FACTOR_DIR / type_i / f"{name}.parquet"
    if not path.exists():
        st.error(f"因子文件不存在: {path}")
        return pd.DataFrame()
    return pd.read_parquet(path)

@st.cache_data
def load_factor_description(type_i: str, name: str) -> Dict[str, Any]:
    """加载因子描述文件"""
    if not DESC_PATH.exists():
        return {}
    with open(DESC_PATH, "r", encoding="utf-8") as f:
        desc_dict = yaml.safe_load(f) or {}
    return desc_dict.get(type_i, {}).get(name, {})

# ------------------------------------------------------------------------
# 2. Computation Logic
# ------------------------------------------------------------------------
@st.cache_data
def compute_ic(
    data: pd.DataFrame, 
    factor_df: pd.DataFrame, 
    ret_nd: List[int], 
    ic_type: Literal['IC', 'Rank-IC']
) -> pd.DataFrame:
    """计算 IC 或 Rank-IC"""
    evaluator = EVALUATION(data, factor_df, ret_nd)
    method = 'pearson' if ic_type.lower() == 'ic' else 'spearman'
    return evaluator.calc_IC(method)

@st.cache_data
def compute_grouped(
    data: pd.DataFrame, 
    factor_df: pd.DataFrame, 
    ret_nd: List[int], 
    quantile: Optional[int] = 10, 
    bins: Optional[int] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """计算分组收益和描述统计"""
    evaluator = EVALUATION(data, factor_df, ret_nd)
    return evaluator.calc_grouped(quantile, bins)

def calculate_hedged_curve(
    ret_series: pd.Series, 
    ret_horizon: int, 
    direction: str = 'L-S'
) -> pd.DataFrame:
    """
    计算分组累计净值及多空对冲净值
    逻辑优化：先算出收益率序列，再进行 cumprod
    """
    # 1. 原始分组收益 (ret_series 是 forward return)
    # 假设输入 ret_series index 是日期, columns 是组别
    # 需要将 forward return shift 回去对齐持有期，这里假设传入的已经是处理好的单期收益
    # 如果 evaluator.calc_grouped 返回的是持有期收益(例如5日收益)，绘图时需要注意频率
    
    # 简单的复利计算: (1+r).cumprod()
    cum_nav = (ret_series + 1).cumprod()
    
    # 2. 计算多空对冲 (Long - Short)
    # 对冲收益率 = 多头组收益率 - 空头组收益率 (不考虑资金利用率减半，纯纯的 alpha)
    cols = ret_series.columns
    long_col = cols[-1] if direction == 'L-S' else cols[0]
    short_col = cols[0] if direction == 'L-S' else cols[-1]
    
    hedged_ret = ret_series[long_col] - ret_series[short_col]
    hedged_col_name = f"{long_col}-{short_col}"
    
    # 合并数据
    final_df = cum_nav.copy()
    final_df[hedged_col_name] = (hedged_ret + 1).cumprod()
    
    # 3. 归一化：起始点设为 1.0 (在最早日期前补一天)
    start_date = final_df.index[0] - datetime.timedelta(days=1)
    # 创建一行 1.0 的数据
    initial_row = pd.DataFrame(1.0, index=[start_date], columns=final_df.columns)
    final_df = pd.concat([initial_row, final_df]).sort_index()
    
    return final_df.round(4)

# ------------------------------------------------------------------------
# 3. Plotting Functions
# ------------------------------------------------------------------------
def plot_ic_series(ic_df: pd.DataFrame):
    """绘制 IC 时序图"""
    if ic_df.empty:
        st.warning("IC 数据为空")
        return

    # 计算累计 IC
    cum_ic_df = ic_df.cumsum().round(3)
    
    # 准备 X 轴
    x_axis = ic_df.index.strftime("%Y-%m-%d").tolist()
    
    bar = Bar(init_opts=opts.InitOpts(width="100%", height="500px"))
    bar.add_xaxis(x_axis)

    # 添加柱状图 (IC)
    cols = ic_df.columns
    legend_selected = {}
    
    for i, col in enumerate(cols):
        is_active = (i == len(cols) - 1)  # 默认只显示最后一个（22d）
        legend_selected[col] = is_active
        legend_selected[f"Cum{col}"] = is_active
        
        bar.add_yaxis(
            series_name=col,
            y_axis=ic_df[col].round(3).tolist(),
            label_opts=opts.LabelOpts(is_show=False),
            itemstyle_opts=opts.ItemStyleOpts(opacity=0.6 if not is_active else 1.0),
        )

    # 添加折线图 (CumIC) - 右轴
    line = Line()
    line.add_xaxis(x_axis)
    
    for i, col in enumerate(cols):
        is_active = (i == len(cols) - 1)
        line.add_yaxis(
            series_name=f"Cum{col}",
            y_axis=cum_ic_df[col].tolist(),
            is_smooth=True,
            label_opts=opts.LabelOpts(is_show=False),
            yaxis_index=1,
            itemstyle_opts=opts.ItemStyleOpts(opacity=0.6 if not is_active else 1.0),
        )

    # 组合图表
    bar.extend_axis(
        yaxis=opts.AxisOpts(
            name="Cum IC", type_="value", position="right", 
            splitline_opts=opts.SplitLineOpts(is_show=False)
        )
    )
    bar.overlap(line)
    bar.set_global_opts(
        title_opts=opts.TitleOpts(title="因子 IC 时序 & 累计 IC"),
        xaxis_opts=opts.AxisOpts(type_="category"),
        yaxis_opts=opts.AxisOpts(name="IC Value", splitline_opts=opts.SplitLineOpts(is_show=True)),
        tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
        datazoom_opts=[opts.DataZoomOpts(range_start=0, range_end=100)],
        legend_opts=opts.LegendOpts(selected_map=legend_selected, pos_top="5%")
    )
    
    st_pyecharts(bar, height="500px")

def plot_factor_distribution(desc_df: pd.DataFrame):
    """绘制因子分布图 (Bar + Kline)"""
    if desc_df.empty:
        return

    # 数据预处理
    df = desc_df.copy()
    x_axis = df.index.astype(str).tolist()
    counts = df['count'].astype(int).tolist()
    
    # Kline data: [open, close, low, high] -> [25%, 75%, min, max]
    ohlc = df[['25%', '75%', 'min', 'max']].values.tolist()

    # 1. Bar (Counts)
    bar = Bar()
    bar.add_xaxis(x_axis)
    bar.add_yaxis(
        "样本数", counts, 
        yaxis_index=0,
        itemstyle_opts=opts.ItemStyleOpts(color="#91cc75", opacity=0.6)
    )

    # 2. Kline (Distribution)
    kline = Kline()
    kline.add_xaxis(x_axis)
    kline.add_yaxis(
        "因子分布", ohlc, 
        yaxis_index=1,
        itemstyle_opts=opts.ItemStyleOpts(color="#5470c6", color0="#5470c6", border_color="#5470c6", border_color0="#5470c6")
    )

    # 3. Combine
    bar.overlap(kline)
    bar.extend_axis(
        yaxis=opts.AxisOpts(
            name="因子值", position="right", 
            splitline_opts=opts.SplitLineOpts(is_show=False)
        )
    )
    bar.set_global_opts(
        title_opts=opts.TitleOpts(title=""),
        xaxis_opts=opts.AxisOpts(name="Group"),
        yaxis_opts=opts.AxisOpts(name="Count", position="left"),
        tooltip_opts=opts.TooltipOpts(
            trigger="axis", 
            axis_pointer_type="cross",
            # 自定义 tooltip 逻辑保持不变或简化
            formatter=JsCode(
                """
                function (params) {
                    let res = '<b>Group: ' + params[0].axisValue + '</b><br/>';
                    params.forEach(function (item) {
                        if (item.seriesType === 'candlestick') {
                            res += item.marker + item.seriesName + '<br/>' +
                                'Max: ' + item.data[4].toFixed(3) + '<br/>' +
                                '75%: ' + item.data[2].toFixed(3) + '<br/>' +
                                '25%: ' + item.data[1].toFixed(3) + '<br/>' +
                                'Min: ' + item.data[3].toFixed(3) + '<br/>';
                        } else {
                            res += item.marker + item.seriesName + ': ' + item.data + '<br/>';
                        }
                    });
                    return res;
                }
                """
            )
        )
    )
    st_pyecharts(bar, height="400px")

def plot_cumulative_returns(nav_df: pd.DataFrame):
    """绘制分组累计收益曲线"""
    if nav_df.empty:
        return

    line = Line()
    x_axis = nav_df.index.strftime("%Y-%m-%d").tolist()
    line.add_xaxis(x_axis)

    cols = nav_df.columns
    n_groups = len(cols) - 1 # 最后一列是对冲
    
    # 颜色映射
    color_map = [colors.to_hex(cm.coolwarm(i / (n_groups - 1))) for i in range(n_groups)] if n_groups > 1 else ["#5470c6"]
    
    for i, col in enumerate(cols):
        is_hedged = (i == len(cols) - 1)
        
        # 样式配置
        if is_hedged:
            c = "black"
            width = 2.5
            opacity = 1.0
            line_type = "dashed"
        else:
            c = color_map[i]
            width = 2
            opacity = 1.0 if i in [0, n_groups-1] else 0.3 # 突出首尾组
            line_type = "solid"

        line.add_yaxis(
            series_name=col,
            y_axis=nav_df[col].tolist(),
            is_smooth=False,
            symbol="none",
            linestyle_opts=opts.LineStyleOpts(width=width, opacity=opacity, color=c, type_=line_type),
            itemstyle_opts=opts.ItemStyleOpts(color=c)
        )

    line.set_global_opts(
        title_opts=opts.TitleOpts(title="分组累计净值曲线"),
        xaxis_opts=opts.AxisOpts(type_="category"),
        yaxis_opts=opts.AxisOpts(name="Net Value", is_scale=True, splitline_opts=opts.SplitLineOpts(is_show=True)),
        tooltip_opts=opts.TooltipOpts(trigger="axis"),
        datazoom_opts=[opts.DataZoomOpts(range_start=0, range_end=100)],
    )
    st_pyecharts(line, height="600px")


# ------------------------------------------------------------------------
# 4. Main Application
# ------------------------------------------------------------------------
def main():
    # --- Sidebar Control ---
    st.sidebar.title("Configuration")
    
    # Factor Selection
    st.sidebar.subheader("1. 因子选择")
    if not FACTOR_DIR.exists():
        st.sidebar.error(f"目录不存在: {FACTOR_DIR}")
        return

    factor_types = [d.name for d in FACTOR_DIR.iterdir() if d.is_dir()]
    selected_type = st.sidebar.selectbox("因子大类", factor_types, index=1 if factor_types else None)
    
    factor_names = []
    if selected_type:
        type_path = FACTOR_DIR / selected_type
        factor_names = [f.stem for f in type_path.glob("*.parquet")]
    selected_name = st.sidebar.selectbox("具体因子", factor_names)

    # Date Selection
    st.sidebar.subheader("2. 时间范围")
    # 默认值，实际应从数据中获取
    default_start = datetime.date(2024, 1, 1)
    default_end = datetime.date.today()
    date_range = st.sidebar.date_input("选择日期区间", [default_start, default_end])
    
    if len(date_range) == 2:
        start_date, end_date = date_range
        start_date_str = start_date.strftime('%Y-%m-%d')
        end_date_str = end_date.strftime('%Y-%m-%d')
    else:
        st.sidebar.warning("请选择完整的起止日期")
        return

    # Analysis Params
    st.sidebar.subheader("3. 分析参数")
    ic_mode = st.sidebar.radio("IC 类型", ['IC', 'Rank-IC'], horizontal=True)
    
    ret_lags_str = st.sidebar.text_input("收益率周期 (逗号分隔)", "1, 5, 10, 22")
    try:
        ret_nds = [int(x.strip()) for x in ret_lags_str.split(',') if x.strip().isdigit()]
    except:
        ret_nds = [1, 5, 10]
        
    group_mode = st.sidebar.selectbox("分组方式", ["Quantile", "Bins"])
    group_num = st.sidebar.number_input("分组数量", min_value=2, max_value=50, value=10)

    # --- Main Content ---
    st.title(f"{selected_name}")
    st.markdown("___")

    # 1. Load Data
    with st.spinner("Loading Data..."):
        full_data = load_base_data()
        full_factor = load_factor_data(selected_type, selected_name)
        
        if full_data.empty or full_factor.empty:
            st.error("数据加载失败")
            return

        # Slicing
        data = full_data.loc[start_date_str:end_date_str]
        factor_df = full_factor.loc[start_date_str:end_date_str]
        
        if data.empty or factor_df.empty:
            st.warning("选定区间无数据")
            return

    # 2. Factor Description
    st.subheader("📌 因子描述")
    desc = load_factor_description(selected_type, selected_name)
    if desc:
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown(f"**Description**: {desc.get('description', 'N/A')}")
            st.markdown(f"**Formula**:")
            if desc.get('formula'):
                st.latex(desc['formula'])
        with c2:
            st.markdown(f"**Category**: `{desc.get('category', 'N/A')}`")
            st.markdown(f"**Reference**: `{desc.get('reference', 'N/A')}`")
    
    with st.expander("查看原始数据 (10 Rows)"):
        st.dataframe(factor_df.head(10).style.format("{:.4f}"))

    # 3. IC Analysis
    st.markdown("---")
    st.subheader("📊 IC 分析")
    
    ic_df = compute_ic(data, factor_df, ret_nds, ic_mode)
    # 按时间切片，因为 EVALUATION 计算可能包含所有时间
    ic_df = ic_df.loc[start_date_str:end_date_str]
    plot_ic_series(ic_df)
    
    # IC 统计表
    st.markdown("**IC 统计摘要**")
    ic_stats = pd.DataFrame({
        'Mean': ic_df.mean(),
        'Std': ic_df.std(),
        'IR': ic_df.mean() / ic_df.std(),
        'Win Rate': (ic_df > 0).mean()
    }).T
    # st.dataframe(ic_stats.style.format("{:.3f}"))#.background_gradient(cmap='RdYlGn', axis=1)

    # 获取 seaborn 的色板对象
    cm = sns.diverging_palette(240, 10, as_cmap=True)
    html_string = ic_stats.style.format("{:.3f}").background_gradient(cmap=cm, axis=1).set_properties(**{'font-size': '18px', 'text-align': 'center'}).to_html()
    # 这一步是为了让表头也变大
    html_string = html_string.replace('<th>', '<th style="font-size: 22px; text-align: center">')
    st.markdown(html_string, unsafe_allow_html=True)



    # 4. Grouped Analysis
    st.markdown("---")
    st.subheader("📈 分组回测")

    params = {'quantile': group_num, 'bins': None} if group_mode == "Quantile" else {'quantile': None, 'bins': group_num}
    
    desc_df, ret_grouped_df = compute_grouped(data, factor_df, ret_nds, **params)
    
    # 4.1 分布图
    st.markdown("#### 因子分层分布")
    plot_factor_distribution(desc_df)
    
    # 4.2 净值曲线
    st.markdown("#### 分组累计净值")
    cols = st.columns(5)
    with cols[0]:
        selected_lag = st.selectbox("选择回测周期 (Ret Lag)", ret_grouped_df.columns, index=0)
    with cols[1]:
        ls_dir = st.radio("对冲方向", ["Long-Short (L-S)", "Short-Long (S-L)"], horizontal=True)
    direction_code = 'L-S' if ls_dir.startswith('L') else 'S-L'

    # 处理收益率数据
    # 假设 ret_grouped_df 是 MultiIndex 或者列名包含周期信息
    # 这里根据原代码逻辑提取特定周期的 Series
    try:
        # 提取特定周期的分组收益，假设结构为: Index=Date, Columns=[Lag1_G1, Lag1_G2...] 或 MultiIndex
        # 原代码逻辑较为特定，这里做通用假设：ret_grouped_df 列名为 '1d', '5d' 等，值为 list 或 dict
        # 但通常 grouped_ret 是 DataFrame: index=date, columns=MultiIndex(lag, group)
        
        # 假设 evaluator 返回的是：列为 (lag, group) 的 DataFrame
        if isinstance(ret_grouped_df.columns, pd.MultiIndex):
            # 取出选定 lag 的数据
            subset = ret_grouped_df[selected_lag] # 得到 columns 为 group 的 df
        else:
            # 兼容原代码的某些特定返回结构，如果 evaluator 返回的是 Series 包含 dict 等
            # 这里暂时保留原代码逻辑的影子，但建议 evaluator 返回标准 DF
            # 下面模拟原代码的 unstack().T 逻辑，视实际数据结构而定
            # 假设: ret_grouped_df 是 index=date, columns=lag, values=分组收益Series
            pass 
            # ！！！注意：由于看不到 EVALUATION 的内部实现，这里使用原代码逻辑进行适配
            subset = ret_grouped_df[selected_lag].unstack().T.dropna()
        
        # 采样频率处理：如果持有期是 5天，理论上应每5天调仓，或者看成重叠收益
        # 为了展示简单，这里按日展示，但需注意复利逻辑
        ret_horizon_days = int(''.join(filter(str.isdigit, str(selected_lag))))
        
        # 重采样以匹配持有期 (可选，原代码有 ::int(selected_nd[:-1]) 逻辑)
        # 如果是重叠收益，直接 cumprod 会夸大。如果是单期独立收益，需要降采样。
        # 采用原代码逻辑：降采样
        subset_resampled = subset.iloc[::ret_horizon_days]
        
        nav_data = calculate_hedged_curve(subset_resampled, ret_horizon_days, direction_code)
        
        # st.markdown(f"#### 分组累计净值 ({selected_lag}, {direction_code})")
        plot_cumulative_returns(nav_data)
        
    except Exception as e:
        st.error(f"处理分组收益数据时出错: {e}")
        st.write("Raw Data Debug:", ret_grouped_df.head())


main()