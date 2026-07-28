import ForceGraph3D from '3d-force-graph';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import SpriteText from 'three-spritetext';

export interface CmekgGraphNode {
  id: string;
  name: string;
  type: string;
  relation: string;
  color?: string;
  val?: number;
  level?: 0 | 1 | 2;
  isRoot?: boolean;
  isBranchHub?: boolean;
  isBranchAnchor?: boolean;
  x?: number;
  y?: number;
  z?: number;
  fx?: number;
  fy?: number;
  fz?: number;
  vx?: number;
  vy?: number;
  vz?: number;
}

export interface CmekgGraphLink {
  source: string | CmekgGraphNode;
  target: string | CmekgGraphNode;
  relation: string;
  color?: string;
  label?: string;
  isBranchLink?: boolean;
  isBranchStem?: boolean;
}

interface Props<NodeType extends CmekgGraphNode, LinkType extends CmekgGraphLink> {
  data: {
    nodes: NodeType[];
    links: LinkType[];
  };
  width: number;
  height: number;
  layoutKey: string;
  visibleRelations: Set<string>;
  collapsedRelations: Set<string>;
  hoveredNodeId: string | null;
  selectedNodeId?: string | null;
  showSecondaryLinks: boolean;
  onNodeHover: (node: NodeType | null) => void;
  onNodeClick: (node: NodeType) => void;
  onBackgroundClick: () => void;
}

const endpointId = (endpoint: unknown) => {
  if (typeof endpoint === 'string') return endpoint;
  if (endpoint && typeof endpoint === 'object' && 'id' in endpoint) {
    return String(endpoint.id);
  }
  return '';
};

const layoutKeys = ['x', 'y', 'z', 'fx', 'fy', 'fz', 'vx', 'vy', 'vz'] as const;

interface ClusterAnchor {
  x: number;
  y: number;
  z: number;
}

type ClusterForceNode = CmekgGraphNode & {
  vx?: number;
  vy?: number;
  vz?: number;
};

// A dense relation needs a longer stem: otherwise the inner edge of its leaf
// cloud reaches back toward the centre node and visually collapses the star.
const clusterStemDistance = (leafCount: number) =>
  Math.max(420, 410 + Math.sqrt(Math.max(leafCount, 1)) * 16);

// Each relation retains its own point on a sphere around the clinical concept.
// These anchors are only a force target, not rendered nodes, so a category
// stays visually together without adding artificial nodes to the graph.
const buildClusterAnchors = (nodes: CmekgGraphNode[]) => {
  const relations = Array.from(new Set(
    nodes.filter((node) => !node.isRoot).map((node) => node.relation),
  )).sort();
  const leafCounts = new Map<string, number>();
  nodes
    .filter((node) => !node.isRoot && !node.isBranchHub)
    .forEach((node) => {
      leafCounts.set(node.relation, (leafCounts.get(node.relation) || 0) + 1);
    });
  const anchors = new Map<string, ClusterAnchor>();
  const goldenAngle = Math.PI * (3 - Math.sqrt(5));

  relations.forEach((relation, index) => {
    const vertical = 1 - (2 * (index + 0.5)) / relations.length;
    const horizontal = Math.sqrt(1 - vertical * vertical);
    const angle = goldenAngle * index;
    const radius = clusterStemDistance(leafCounts.get(relation) || 0);
    anchors.set(relation, {
      x: Math.cos(angle) * horizontal * radius,
      y: vertical * radius,
      z: Math.sin(angle) * horizontal * radius,
    });
  });
  return anchors;
};

const createClusterForce = (anchors: Map<string, ClusterAnchor>) => {
  let nodes: ClusterForceNode[] = [];
  const force = (alpha: number) => {
    nodes.forEach((node) => {
      if (node.isRoot) return;
      const anchor = anchors.get(node.relation);
      if (!anchor) return;
      // The junction stays on its radial position. Leaves are primarily
      // positioned by their own short link so the group reads as a star,
      // matching CMeKG rather than a compressed colour ball.
      const pull = alpha * (node.isBranchHub ? 0.014 : 0.0018);
      node.vx = (node.vx || 0) + (anchor.x - (node.x || 0)) * pull;
      node.vy = (node.vy || 0) + (anchor.y - (node.y || 0)) * pull;
      node.vz = (node.vz || 0) + (anchor.z - (node.z || 0)) * pull;
    });
  };
  force.initialize = (nextNodes: ClusterForceNode[]) => {
    nodes = nextNodes;
  };
  return force;
};

const collisionRadius = (node: CmekgGraphNode) => {
  if (node.isRoot) return 34;
  if (node.isBranchHub) return 3;
  return 14;
};

// The graph library's default force set does not include collision handling.
// This lightweight 3D pass keeps the leaves readable while the category force
// continues to hold their group around its junction point.
const createCollisionForce = () => {
  let nodes: ClusterForceNode[] = [];
  const force = (alpha: number) => {
    // Spreading is only needed while a new graph is settling. Leaving this
    // pairwise work active at low alpha makes camera navigation feel heavy.
    if (alpha < 0.2) return;
    for (let index = 0; index < nodes.length; index += 1) {
      const current = nodes[index];
      if (!current) continue;
      for (let otherIndex = index + 1; otherIndex < nodes.length; otherIndex += 1) {
        const other = nodes[otherIndex];
        if (!other) continue;
        if (!current.isRoot && !other.isRoot && current.relation !== other.relation) continue;
        const minimumDistance = collisionRadius(current) + collisionRadius(other) + 5;
        let xDistance = ((current.x || 0) + (current.vx || 0)) - ((other.x || 0) + (other.vx || 0));
        let yDistance = ((current.y || 0) + (current.vy || 0)) - ((other.y || 0) + (other.vy || 0));
        let zDistance = ((current.z || 0) + (current.vz || 0)) - ((other.z || 0) + (other.vz || 0));
        let distance = Math.sqrt(xDistance * xDistance + yDistance * yDistance + zDistance * zDistance);
        if (distance >= minimumDistance) continue;
        if (distance < 0.001) {
          // A deterministic nudge resolves two nodes spawned at one position.
          xDistance = (index - otherIndex) * 0.01;
          yDistance = ((index + otherIndex) % 3 - 1) * 0.01;
          zDistance = ((index * 7 + otherIndex) % 5 - 2) * 0.01;
          distance = Math.sqrt(xDistance * xDistance + yDistance * yDistance + zDistance * zDistance);
        }
        const adjustment = ((minimumDistance - distance) / distance) * 0.42;
        const xVelocity = xDistance * adjustment;
        const yVelocity = yDistance * adjustment;
        const zVelocity = zDistance * adjustment;
        current.vx = (current.vx || 0) + xVelocity;
        current.vy = (current.vy || 0) + yVelocity;
        current.vz = (current.vz || 0) + zVelocity;
        other.vx = (other.vx || 0) - xVelocity;
        other.vy = (other.vy || 0) - yVelocity;
        other.vz = (other.vz || 0) - zVelocity;
      }
    }
  };
  force.initialize = (nextNodes: ClusterForceNode[]) => {
    nodes = nextNodes;
  };
  return force;
};

const RELATION_LABELS: Record<string, string> = {
  symptom: '临床表现',
  medication: '首选药物',
  complication: '并发症',
  surgery: '手术治疗',
  therapy: '治疗方式',
  lab: '实验室检查',
  imaging: '影像学检查',
  endoscopy: '内镜检查',
  exam: '相关检查',
  department: '所属科室',
  routing: '初诊分流',
  diet: '饮食建议',
  related: '相关关系',
};

const disposeLabel = (label: SpriteText) => {
  label.material.map?.dispose();
  label.material.dispose();
};

export function CmekgForceGraph<
  NodeType extends CmekgGraphNode,
  LinkType extends CmekgGraphLink,
>({
  data,
  width,
  height,
  layoutKey,
  visibleRelations,
  collapsedRelations,
  hoveredNodeId,
  selectedNodeId,
  showSecondaryLinks,
  onNodeHover,
  onNodeClick,
  onBackgroundClick,
}: Props<NodeType, LinkType>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const nodeCacheRef = useRef(new Map<string, NodeType>());
  const labelCacheRef = useRef(new Map<string, SpriteText>());
  const layoutKeyRef = useRef('');
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout>>();
  const hoverFocusEnabledRef = useRef(true);
  const onNodeHoverRef = useRef(onNodeHover);
  const onNodeClickRef = useRef(onNodeClick);
  const onBackgroundClickRef = useRef(onBackgroundClick);
  const [hoveredLinkEndpoints, setHoveredLinkEndpoints] = useState<{
    source: string;
    target: string;
  } | null>(null);

  onNodeHoverRef.current = onNodeHover;
  onNodeClickRef.current = onNodeClick;
  onBackgroundClickRef.current = onBackgroundClick;

  const debouncedSetHover = useCallback((node: NodeType | null) => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    hoverTimerRef.current = setTimeout(() => onNodeHoverRef.current(node), 90);
  }, []);

  const displayedData = useMemo(() => {
    if (layoutKeyRef.current !== layoutKey) {
      nodeCacheRef.current.clear();
      labelCacheRef.current.forEach(disposeLabel);
      labelCacheRef.current.clear();
      layoutKeyRef.current = layoutKey;
    }

    const visibleNodeIds = new Set(
      data.nodes
        .filter((node) => node.isRoot || (
          visibleRelations.has(node.relation)
          && !collapsedRelations.has(node.relation)
        ))
        .map((node) => node.id),
    );

    const visibleNodes = data.nodes.filter((node) => visibleNodeIds.has(node.id));
    const usesRelationHubs = visibleNodes.some((node) => node.isBranchHub);
    const clusterAnchors = buildClusterAnchors(visibleNodes);
    const clusterIndexes = new Map<string, number>();
    const clusterSizes = new Map<string, number>();
    visibleNodes
      .filter((node) => !node.isRoot && !node.isBranchHub)
      .forEach((node) => {
        clusterSizes.set(node.relation, (clusterSizes.get(node.relation) || 0) + 1);
      });

    const nodes = visibleNodes
      .map((node, index) => {
        const cached = nodeCacheRef.current.get(node.id);
        const next = { ...node } as NodeType;
        // The API pins the root for the old fan layout. CMeKG's radial DAG
        // needs the simulation to own all positions until the user drags.
        layoutKeys.forEach((key) => {
          delete (next as Record<string, unknown>)[key];
        });
        if (cached?.fx != null && cached.fy != null && cached.fz != null) {
          next.x = cached.x;
          next.y = cached.y;
          next.z = cached.z;
          next.fx = cached.fx;
          next.fy = cached.fy;
          next.fz = cached.fz;
        } else if (next.isRoot) {
          next.x = 0;
          next.y = 0;
          next.z = 0;
        } else if (next.isBranchHub) {
          const anchor = clusterAnchors.get(next.relation) || { x: 0, y: 0, z: 0 };
          next.x = anchor.x;
          next.y = anchor.y;
          next.z = anchor.z;
        } else if (usesRelationHubs) {
          const clusterIndex = clusterIndexes.get(next.relation) || 0;
          clusterIndexes.set(next.relation, clusterIndex + 1);
          const anchor = clusterAnchors.get(next.relation) || { x: 0, y: 0, z: 0 };
          const clusterSize = clusterSizes.get(next.relation) || 1;
          const angle = clusterIndex * Math.PI * (3 - Math.sqrt(5));
          const vertical = 1 - (2 * (clusterIndex + 0.5)) / clusterSize;
          const horizontal = Math.sqrt(Math.max(0, 1 - vertical * vertical));
          // Dense categories need a wider shell; otherwise dozens of leaves
          // occupy the same apparent screen area and turn into a solid ball.
          const localRadius = 115 + Math.sqrt(clusterSize) * 16;
          next.x = anchor.x + Math.cos(angle) * horizontal * localRadius;
          next.y = anchor.y + vertical * localRadius;
          next.z = anchor.z + Math.sin(angle) * horizontal * localRadius;
        } else {
          const angle = index * Math.PI * (3 - Math.sqrt(5));
          const radius = 18 + Math.sqrt(index) * 12;
          next.x = Math.cos(angle) * radius;
          next.y = Math.sin(angle) * radius;
          next.z = ((index % 5) - 2) * 10;
        }
        return next;
      });

    const links = data.links
      .filter((link) => {
        const source = endpointId(link.source);
        const target = endpointId(link.target);
        if (!visibleNodeIds.has(source) || !visibleNodeIds.has(target)) return false;
        if (!visibleRelations.has(link.relation)) return false;
        if (link.isBranchStem) return true;
        return !collapsedRelations.has(link.relation);
      })
      .map((link) => ({
        ...link,
        source: endpointId(link.source),
        target: endpointId(link.target),
      })) as LinkType[];

    return { nodes, links };
  }, [collapsedRelations, data, layoutKey, visibleRelations]);

  const clusterAnchors = useMemo(
    () => buildClusterAnchors(displayedData.nodes),
    [displayedData.nodes],
  );
  // Hovering a sphere must not reconfigure the graph. Details are opened by
  // clicking; keeping hover passive makes rotation consistently smooth.
  hoverFocusEnabledRef.current = false;

  useEffect(() => {
    if (!hoverFocusEnabledRef.current && hoveredNodeId) onNodeHoverRef.current(null);
  }, [displayedData.nodes.length, hoveredNodeId]);

  const focusState = useMemo(() => {
    const nodeIds = new Set<string>();
    if (hoveredNodeId) {
      nodeIds.add(hoveredNodeId);
      displayedData.links.forEach((link) => {
        const source = endpointId(link.source);
        const target = endpointId(link.target);
        if (source !== hoveredNodeId && target !== hoveredNodeId) return;
        nodeIds.add(source);
        nodeIds.add(target);
      });
    } else if (hoveredLinkEndpoints) {
      nodeIds.add(hoveredLinkEndpoints.source);
      nodeIds.add(hoveredLinkEndpoints.target);
    }
    return { nodeIds: nodeIds.size > 0 ? nodeIds : null };
  }, [displayedData.links, hoveredLinkEndpoints, hoveredNodeId]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || graphRef.current) return;

    const graph = new ForceGraph3D(container, {
      controlType: 'trackball',
      rendererConfig: {
        antialias: false,
        alpha: true,
        powerPreference: 'high-performance',
      },
    })
      .backgroundColor('#101a22')
      .showNavInfo(false)
      .numDimensions(3)
      .nodeRelSize(20)
      .nodeOpacity(0.86)
      .linkOpacity(0.95)
      .linkWidth(0.9)
      .linkDirectionalParticles(0)
      .linkDirectionalArrowLength(4.2)
      .linkDirectionalArrowRelPos(1)
      .linkCurvature(0)
      // Nodes remain draggable on press; passive hover does not change layout.
      .enableNodeDrag(true)
      .enableNavigationControls(true)
      .nodeLabel((node: any) => node.name)
      .onNodeHover((node: any) => {
        if (!hoverFocusEnabledRef.current) return;
        if (node) setHoveredLinkEndpoints(null);
        debouncedSetHover(node);
      })
      // Link-hover changes rapidly while rotating through a dense graph and
      // would otherwise trigger a React update for nearly every mouse move.
      .onLinkHover(() => {})
      .onNodeClick((node: any) => onNodeClickRef.current(node))
      .onBackgroundClick(() => {
        setHoveredLinkEndpoints(null);
        onBackgroundClickRef.current();
      })
      .d3AlphaDecay(0.055)
      .d3VelocityDecay(0.45)
      .warmupTicks(36)
      .cooldownTime(2_500);

    const linkForce = graph.d3Force('link') as {
      distance?: (value: number | ((link: LinkType) => number)) => unknown;
    } | undefined;
    linkForce?.distance?.(300);

    // High-DPI screens otherwise ask WebGL to draw four times as many pixels
    // for every sphere, arrow and text sprite. This cap retains crisp labels
    // while keeping navigation responsive on ordinary laptops.
    const renderer = graph.renderer?.();
    renderer?.setPixelRatio?.(Math.min(window.devicePixelRatio || 1, 1.25));

    graphRef.current = graph;
    graph.cameraPosition({ x: 0, y: 0, z: 650 }, { x: 0, y: 0, z: 0 }, 0);
    return () => {
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
      labelCacheRef.current.forEach(disposeLabel);
      labelCacheRef.current.clear();
      graph._destructor();
      graphRef.current = null;
      container.replaceChildren();
    };
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph || width <= 0 || height <= 0) return;
    graph.width(width).height(height);
  }, [height, width]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.graphData(displayedData);
    const linkForce = graph.d3Force('link') as {
      distance?: (value: number | ((link: LinkType) => number)) => unknown;
    } | undefined;
    const usesRelationHubs = displayedData.nodes.some((node) => node.isBranchHub);
    const isDepartmentGraph = displayedData.nodes.some(
      (node) => node.isRoot && node.type === 'Department',
    );
    const relationCounts = new Map<string, number>();
    displayedData.nodes
      .filter((node) => !node.isRoot && !node.isBranchHub)
      .forEach((node) => {
        relationCounts.set(node.relation, (relationCounts.get(node.relation) || 0) + 1);
      });
    linkForce?.distance?.(usesRelationHubs
      ? (link: LinkType) => {
        if (link.isBranchStem) {
          return clusterStemDistance(relationCounts.get(link.relation) || 0);
        }
        const count = relationCounts.get(link.relation) || 1;
        return Math.min(260, 115 + Math.sqrt(count) * 16);
      }
      // Department overview has no relation hubs; give its direct spokes the
      // same airy radial spacing while retaining the shared 0.9px fine line.
      : (isDepartmentGraph ? 420 : 300));
  }, [displayedData]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    const usesRelationHubs = displayedData.nodes.some((node) => node.isBranchHub);
    graph.d3Force(
      'relation-cluster',
      usesRelationHubs ? createClusterForce(clusterAnchors) : null,
    );
    graph.d3Force(
      'node-collision',
      usesRelationHubs ? createCollisionForce() : null,
    );
  }, [clusterAnchors, displayedData.nodes]);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;

    const isFocusedLink = (link: LinkType) => {
      const source = endpointId(link.source);
      const target = endpointId(link.target);
      if (hoveredNodeId) return source === hoveredNodeId || target === hoveredNodeId;
      if (!hoveredLinkEndpoints) return false;
      return (
        source === hoveredLinkEndpoints.source
        && target === hoveredLinkEndpoints.target
      ) || (
        source === hoveredLinkEndpoints.target
        && target === hoveredLinkEndpoints.source
      );
    };
    const isDimmedNode = (node: NodeType) =>
      Boolean(focusState.nodeIds && !focusState.nodeIds.has(node.id));
    const nodeColor = (node: NodeType) => {
      if (selectedNodeId === node.id) return '#ffffff';
      if (isDimmedNode(node)) return 'rgba(204, 204, 204, 0.38)';
      return node.color || '#63c4c7';
    };
    const linkColor = (link: LinkType) => {
      if (!focusState.nodeIds) {
        return 'rgba(190, 205, 214, 0.72)';
      }
      return isFocusedLink(link)
        ? '#edf3f5'
        : 'rgba(130, 140, 145, 0.12)';
    };

    const shouldShowLabel = () => true;

    const makeLabel = (node: NodeType) => {
      if (node.isBranchHub) return null;
      const cached = labelCacheRef.current.get(node.id);
      if (cached) {
        cached.visible = shouldShowLabel();
        return cached;
      }

      const isDepartmentRoot = node.isRoot && node.type === 'Department';
      const label = new SpriteText(node.name, isDepartmentRoot ? 17 : node.isRoot ? 15 : 11.5, '#ffffff');
      label.fontFace = '"Microsoft YaHei", "PingFang SC", sans-serif';
      label.fontWeight = node.isRoot ? '700' : '500';
      label.backgroundColor = false;
      label.padding = 0;
      label.strokeWidth = isDepartmentRoot ? 0.55 : 0.32;
      label.strokeColor = 'rgba(7, 31, 39, 0.88)';
      label.material.depthWrite = false;
      label.visible = shouldShowLabel();
      labelCacheRef.current.set(node.id, label);
      return label;
    };

    displayedData.nodes.forEach((node) => {
      const label = labelCacheRef.current.get(node.id);
      if (label) label.visible = shouldShowLabel();
    });

    graph
      .nodeVal((node: NodeType) => {
        if (node.isRoot) return 10;
        if (node.isBranchHub) return node.val || 0.01;
        return 0.5;
      })
      .nodeColor(nodeColor)
      .nodeThreeObject(makeLabel)
      .nodeThreeObjectExtend(true)
      .linkColor(linkColor)
      .linkWidth((link: LinkType) => {
        if (isFocusedLink(link)) return 1.1;
        return 0.9;
      })
      .linkDirectionalArrowColor(linkColor)
      .linkVisibility((link: LinkType) =>
        Boolean(link.isBranchLink || showSecondaryLinks || isFocusedLink(link)));
    graph.resumeAnimation();
  }, [
    displayedData.nodes,
    focusState,
    hoveredLinkEndpoints,
    hoveredNodeId,
    selectedNodeId,
    showSecondaryLinks,
  ]);

  const resetViewport = () => {
    const graph = graphRef.current;
    if (!graph) return;
    graph.cameraPosition({ x: 0, y: 0, z: 650 }, { x: 0, y: 0, z: 0 }, 250);
  };

  return (
    <>
      <div ref={containerRef} className="kg-cmekg-graph" aria-label="三维医学知识图谱" />
      <button type="button" className="kg-graph-reset" onClick={resetViewport}>
        <span aria-hidden="true">↺</span>
        重新居中
      </button>
    </>
  );
}
