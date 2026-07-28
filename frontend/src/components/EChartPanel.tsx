import { BarChartOutlined } from '@ant-design/icons';
import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts';
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  TransformComponent,
} from 'echarts/components';
import * as echarts from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useEffect, useRef } from 'react';

import type { ChartUiData } from '../api/types';
import { sanitizeChartOption } from './chartOption';

interface Props {
  data: ChartUiData;
}

echarts.use([
  BarChart,
  LineChart,
  PieChart,
  ScatterChart,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  TitleComponent,
  TooltipComponent,
  TransformComponent,
  CanvasRenderer,
]);

export function EChartPanel({ data }: Props) {
  const host = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!host.current) return;
    const chart = echarts.init(host.current, undefined, { renderer: 'canvas' });
    chart.setOption(sanitizeChartOption(data), { notMerge: true });
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(host.current);
    return () => {
      observer.disconnect();
      chart.dispose();
    };
  }, [data]);

  return (
    <section className="chart-panel">
      <header>
        <div>
          <span>动态分析</span>
          <h3>{data.title || '业务数据视图'}</h3>
        </div>
        <BarChartOutlined />
      </header>
      <div ref={host} className="chart-canvas" role="img" aria-label={data.title || '业务图表'} />
    </section>
  );
}
