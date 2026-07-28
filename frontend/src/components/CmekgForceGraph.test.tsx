// @vitest-environment jsdom

import { act, cleanup, fireEvent, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const forceGraphMock = vi.hoisted(() => {
  const graph: Record<string, ReturnType<typeof vi.fn>> = {};
  const linkForce = { distance: vi.fn(), strength: vi.fn() };
  const chainMethods = [
    'backgroundColor',
    'showNavInfo',
    'numDimensions',
    'nodeRelSize',
    'nodeResolution',
    'nodeOpacity',
    'linkOpacity',
    'linkWidth',
    'linkDirectionalParticles',
    'enableNodeDrag',
    'enableNavigationControls',
    'nodeLabel',
    'onNodeHover',
    'onLinkHover',
    'onNodeClick',
    'onBackgroundClick',
    'onNodeDragEnd',
    'onNodeDrag',
    'd3AlphaDecay',
    'd3VelocityDecay',
    'warmupTicks',
    'cooldownTime',
    'width',
    'height',
    'graphData',
    'd3ReheatSimulation',
    'cameraPosition',
    'zoomToFit',
    'nodeVal',
    'nodeColor',
    'nodeThreeObject',
    'nodeThreeObjectExtend',
    'linkColor',
    'linkDirectionalArrowLength',
    'linkDirectionalArrowRelPos',
    'linkDirectionalArrowColor',
    'linkCurvature',
    'linkThreeObjectExtend',
    'linkVisibility',
    'linkThreeObject',
    'linkPositionUpdate',
    'resumeAnimation',
  ];

  chainMethods.forEach((method) => {
    graph[method] = vi.fn(() => graph);
  });
  graph.d3Force = vi.fn((name: string) => {
    if (name === 'link') return linkForce;
    return undefined;
  });
  graph._destructor = vi.fn();

  const constructor = vi.fn(function ForceGraphMock() {
    return graph;
  });

  return {
    constructor,
    graph,
    linkForce,
  };
});

vi.mock('3d-force-graph', () => ({ default: forceGraphMock.constructor }));

import { CmekgForceGraph } from './CmekgForceGraph';

const baseProps = {
  data: {
    nodes: [
      { id: '临床心理科', name: '临床心理科', type: 'Department', relation: 'related', isRoot: true },
      { id: '焦虑障碍', name: '焦虑障碍', type: 'Disease', relation: 'routed' },
    ],
    links: [
      { source: '焦虑障碍', target: '临床心理科', relation: 'routed' },
    ],
  },
  width: 1200,
  height: 700,
  layoutKey: '临床心理科',
  visibleRelations: new Set(['related', 'routed']),
  collapsedRelations: new Set<string>(),
  hoveredNodeId: null,
  selectedNodeId: null,
  showSecondaryLinks: false,
  onNodeHover: vi.fn(),
  onNodeClick: vi.fn(),
  onBackgroundClick: vi.fn(),
};

describe('CmekgForceGraph viewport stability', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    Object.values(forceGraphMock.graph).forEach((mock) => mock.mockClear());
    forceGraphMock.linkForce.distance.mockClear();
    forceGraphMock.linkForce.strength.mockClear();
    forceGraphMock.constructor.mockClear();
  });

  afterEach(() => {
    cleanup();
    vi.runOnlyPendingTimers();
    vi.useRealTimers();
  });

  it('seeds the camera without automatically changing the viewport after layout', () => {
    render(<CmekgForceGraph {...baseProps} />);

    expect(forceGraphMock.graph.width).toHaveBeenCalledWith(1200);
    expect(forceGraphMock.graph.height).toHaveBeenCalledWith(700);
    expect(forceGraphMock.graph.cameraPosition).toHaveBeenCalledWith(
      { x: 0, y: 0, z: 650 },
      { x: 0, y: 0, z: 0 },
      0,
    );
    expect(forceGraphMock.graph.graphData).toHaveBeenCalled();
    expect(forceGraphMock.graph.d3ReheatSimulation).not.toHaveBeenCalled();
    expect(forceGraphMock.constructor).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({ controlType: 'trackball' }),
    );
    expect(forceGraphMock.graph.nodeRelSize).toHaveBeenLastCalledWith(20);
    expect(forceGraphMock.graph.nodeThreeObjectExtend).toHaveBeenLastCalledWith(true);
    expect(forceGraphMock.graph.nodeThreeObject).toHaveBeenCalledWith(expect.any(Function));
    expect(forceGraphMock.graph.linkWidth).toHaveBeenLastCalledWith(expect.any(Function));
    expect(forceGraphMock.graph.linkDirectionalArrowLength).toHaveBeenCalledWith(4.2);
    expect(forceGraphMock.graph.linkDirectionalArrowRelPos).toHaveBeenCalledWith(1);
    expect(forceGraphMock.linkForce.distance).toHaveBeenCalledWith(300);

    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    expect(forceGraphMock.graph.zoomToFit).not.toHaveBeenCalled();
  });

  it('keeps the viewport unchanged when the canvas is resized', () => {
    const view = render(<CmekgForceGraph {...baseProps} />);
    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    view.rerender(<CmekgForceGraph {...baseProps} width={900} height={500} />);
    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    expect(forceGraphMock.graph.width).toHaveBeenLastCalledWith(900);
    expect(forceGraphMock.graph.height).toHaveBeenLastCalledWith(500);
    expect(forceGraphMock.graph.zoomToFit).not.toHaveBeenCalled();
  });

  it('lets the user recover the camera with the recenter control', () => {
    const view = render(<CmekgForceGraph {...baseProps} />);

    fireEvent.click(view.getByRole('button', { name: '重新居中' }));
    expect(forceGraphMock.graph.cameraPosition).toHaveBeenLastCalledWith(
      { x: 0, y: 0, z: 650 },
      { x: 0, y: 0, z: 0 },
      250,
    );
    expect(forceGraphMock.graph.d3ReheatSimulation).not.toHaveBeenCalled();
  });
});
