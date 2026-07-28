import { describe, expect, it } from 'vitest';

import type { ChartUiData } from '../api/types';
import { sanitizeChartOption } from './chartOption';

describe('sanitizeChartOption', () => {
  it('forces rich-text tooltips for server-provided options', () => {
    const option = sanitizeChartOption({
      type: 'chart',
      option: { series: [{ type: 'bar', data: [1, 2] }] },
    });

    expect(option.tooltip).toEqual({ trigger: 'axis', renderMode: 'richText' });
  });

  it('rejects executable-style formatter fields', () => {
    const data = {
      type: 'chart',
      option: { tooltip: { formatter: '<img src=x onerror=alert(1)>' } },
    } as ChartUiData;

    expect(() => sanitizeChartOption(data)).toThrow('formatter');
  });
});
