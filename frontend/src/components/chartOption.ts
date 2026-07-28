import type { EChartsOption } from 'echarts/types/dist/shared';

import type { ChartUiData, JsonValue } from '../api/types';

export function sanitizeChartOption(data: ChartUiData): EChartsOption {
  if (data.option) {
    assertSafeObject(data.option);
    return {
      ...(data.option as EChartsOption),
      tooltip: { trigger: 'axis', renderMode: 'richText' },
    };
  }
  const series = (data.series || []).slice(0, 12).map((item) => ({
    name: item.name,
    type: item.type || 'line',
    smooth: item.type !== 'bar',
    data: item.data.slice(0, 2_000),
  }));
  return {
    animationDuration: 520,
    color: ['#1f6b62', '#d98635', '#547886', '#925d71'],
    grid: { left: 18, right: 18, top: 28, bottom: 18, containLabel: true },
    tooltip: { trigger: 'axis', renderMode: 'richText' },
    xAxis: {
      type: 'category',
      data: (data.xAxis || []).slice(0, 2_000),
      axisLine: { lineStyle: { color: '#c8d4cf' } },
      axisLabel: { color: '#536562' },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: '#e5ebe8' } },
      axisLabel: { color: '#536562' },
    },
    series,
  };
}

function assertSafeObject(value: Record<string, JsonValue>): void {
  const stack: JsonValue[] = [value];
  let visited = 0;
  while (stack.length) {
    const current = stack.pop();
    if (current === null || typeof current !== 'object') continue;
    if (++visited > 20_000) throw new Error('图表配置超过安全复杂度');
    if (Array.isArray(current)) {
      stack.push(...current);
      continue;
    }
    for (const [key, nested] of Object.entries(current)) {
      if (['__proto__', 'prototype', 'constructor', 'formatter'].includes(key)) {
        throw new Error(`图表配置包含不允许的字段：${key}`);
      }
      stack.push(nested);
    }
  }
}
