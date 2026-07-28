import {
  ApartmentOutlined,
  CloseOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MedicineBoxOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { Alert, Input, Spin, Tag } from 'antd';
import { CmekgForceGraph } from './CmekgForceGraph';

// ── Types ─────────────────────────────────────────────────────────

interface KgNode {
  type: string;
  name: string;
  desc?: string;
  diseaseCount?: number;
  publishedDiseaseCount?: number;
  referenceDiseaseCount?: number;
  knowledgeStatus?: 'PUBLISHED' | 'STANDARDIZED' | 'CATALOG_ONLY' | 'REFERENCE_ONLY';
}

interface KgLink {
  source: string;
  target: string;
  rel_type: string;
  evidence?: 'PUBLISHED' | 'REFERENCE_ONLY';
}

interface GraphData {
  nodes: KgNode[];
  links: KgLink[];
}

interface SearchResult {
  type: string;
  name: string;
  desc: string;
  knowledgeStatus?: 'PUBLISHED' | 'STANDARDIZED' | 'CATALOG_ONLY';
}

// ── Config ────────────────────────────────────────────────────────

const TYPE_COLORS: Record<string, string> = {
  KnowledgeHub: '#276d7c',
  Disease: '#2d6cdf',
  Symptom: '#d95775',
  Drug: '#2f8f6b',
  Exam: '#d28b28',
  Department: '#178c9f',
  Food: '#d97832',
  Therapy: '#8667b4',
};

const TYPE_LABELS: Record<string, string> = {
  KnowledgeHub: '知识库总览',
  Disease: '疾病',
  Symptom: '症状',
  Drug: '药品',
  Exam: '检查',
  Department: '科室',
  Food: '饮食',
  Therapy: '治疗方式',
};

const FALLBACK_RELATION = { label: '相关关系', color: '#84969f' };

const RELATION_CONFIG: Record<string, { label: string; color: string }> = {
  complication: { label: '并发症', color: '#ed6b73' },
  symptom: { label: '临床症状', color: '#e99aae' },
  medication: { label: '药物治疗', color: '#4f8de4' },
  surgery: { label: '手术治疗', color: '#b39ddb' },
  therapy: { label: '其他治疗', color: '#9575cd' },
  lab: { label: '实验室检查', color: '#26c6da' },
  imaging: { label: '影像学检查', color: '#7bc86c' },
  endoscopy: { label: '内镜检查', color: '#a1887f' },
  exam: { label: '一般检查', color: '#e0bd3e' },
  department: { label: '所属科室', color: '#31a6a1' },
  routing: { label: '初诊分流参考', color: '#c7ad2f' },
  diet: { label: '饮食建议', color: '#ffb74d' },
  related: FALLBACK_RELATION,
};

const RELATION_KEYS = Object.keys(RELATION_CONFIG);
const getRelationConfig = (key?: string) => key ? RELATION_CONFIG[key] || FALLBACK_RELATION : FALLBACK_RELATION;

const EXAM_ENDOSCOPY = ['胃镜', '肠镜', '支气管镜', '膀胱镜', '宫腔镜', '关节镜', '喉镜', '腹腔镜', '纵隔镜', '内镜', '镜检'];
const EXAM_IMAGING = ['X线', 'X光', 'CT', '磁共振', 'MRI', '核磁', '超声', 'B超', '彩超', '造影', '钼靶', 'PET', 'ECT', '平片', '摄片', '钡餐', '钡剂', '放射', '血管造影'];
const EXAM_LAB = ['血', '尿', '便', '粪', '生化', '血清', '抗体', '抗原', '酶', '培养', '涂片', '核酸', '基因', '染色体', '免疫', '血糖', '血脂', '电解质', '凝血', '蛋白', '计数', '沉降', '因子'];
const classifyExam = (name = '') => {
  if (EXAM_ENDOSCOPY.some((k) => name.includes(k))) return 'endoscopy';
  if (EXAM_IMAGING.some((k) => name.includes(k))) return 'imaging';
  if (EXAM_LAB.some((k) => name.includes(k))) return 'lab';
  return 'exam';
};
const classifyTherapy = (name = '') =>
  ['手术', '外科', '切除', '移植', '术'].some((k) => name.includes(k)) ? 'surgery' : 'therapy';

const relationKey = (relType?: string, nodeName?: string) => {
  switch (relType) {
    case 'COMPLICATION': return 'complication';
    case 'HAS_SYMPTOM': return 'symptom';
    case 'TREATED_BY': return 'medication';
    case 'REQUIRES_EXAM': return classifyExam(nodeName);
    case 'HAS_THERAPY': return classifyTherapy(nodeName);
    case 'RECOMMENDED_EAT':
    case 'AVOID_EAT':
    case 'RECOMMENDED_RECIPE': return 'diet';
    case 'BELONGS_TO': return 'department';
    case 'ROUTED_TO': return 'routing';
    case 'HAS_DEPARTMENT': return 'department';
    default: return 'related';
  }
};

const QUICK_TAGS = [
  '糖尿病', '高血压', '肺炎', '冠心病', '抑郁症', '胃炎', '肝炎', '肾炎',
];

const DEPT_TAGS = [
  { name: '心内科', color: '#d95775' },
  { name: '呼吸内科', color: '#2d6cdf' },
  { name: '消化内科', color: '#2f8f6b' },
  { name: '神经内科', color: '#8b6bb1' },
  { name: '内分泌科', color: '#d28b28' },
  { name: '风湿免疫科', color: '#178c9f' },
];

// ── Component ─────────────────────────────────────────────────────

interface Props {
  accessToken: string;
  onOpenGovernance?: () => void;
}

const API_BASE = (window.__YUANQI_CONFIG__?.agentApiBaseUrl ?? import.meta.env.VITE_AGENT_API_BASE_URL ?? '').replace(/\/$/, '');

interface GraphNode {
  id: string;
  name: string;
  type: string;
  desc?: string;
  diseaseCount?: number;
  publishedDiseaseCount?: number;
  referenceDiseaseCount?: number;
  val?: number;
  color?: string;
  level?: 0 | 1 | 2;
  relation: string;
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
  knowledgeStatus?: KgNode['knowledgeStatus'];
}

interface GraphLink {
  source: string | GraphNode;
  target: string | GraphNode;
  rel_type?: string;
  relation: string;
  color?: string;
  label?: string;
  evidence?: KgLink['evidence'];
  isBranchLink?: boolean;
  isBranchStem?: boolean;
}

interface RelationGroup {
  key: string;
  nodes: GraphNode[];
}

const endpointName = (value: unknown) => {
  if (typeof value === 'string') return value;
  if (value && typeof value === 'object' && 'id' in value) return String(value.id);
  return '';
};

const relationHubId = (relation: string) => `__relation_hub__${relation}`;

export function KnowledgeGraph({ accessToken, onOpenGovernance }: Props) {
  const chartAreaRef = useRef<HTMLDivElement>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [selectedNode, setSelectedNode] = useState<KgNode | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [collapsedRelations, setCollapsedRelations] = useState<Set<string>>(() => new Set());
  const [loading, setLoading] = useState(false);
  const [graphError, setGraphError] = useState('');
  const [visibleRelations, setVisibleRelations] = useState<Set<string>>(() => new Set(RELATION_KEYS));
  const [viewMode, setViewMode] = useState<'graph' | 'outline'>('graph');
  const [activePerspective, setActivePerspective] = useState<'clinical' | 'overview'>('clinical');
  const [isIndexCollapsed, setIsIndexCollapsed] = useState(false);
  const [showSecondaryLinks, setShowSecondaryLinks] = useState(false);
  const [shownNodeCounts, setShownNodeCounts] = useState<Record<string, number>>({});
  const [departmentTags, setDepartmentTags] = useState(DEPT_TAGS);
  const [graphData, setGraphData] = useState<{ nodes: GraphNode[]; links: GraphLink[] }>({ nodes: [], links: [] });
  const [graphRoot, setGraphRoot] = useState('');
  const [graphSize, setGraphSize] = useState({ width: 0, height: 0 });
  const [nodeCount, setNodeCount] = useState(0);
  const [linkCount, setLinkCount] = useState(0);
  const visualGraphData = useMemo(() => {
    if (!graphRoot || graphData.nodes.length === 0) return graphData;
    // CMeKG renders direct centre-to-entity links. Relation metadata remains
    // available to the legend, but does not introduce synthetic hub nodes.
    const directLinks = graphData.links
      .map((link) => ({
        ...link,
        source: endpointName(link.source),
        target: endpointName(link.target),
      }))
      .filter((link) => link.source === graphRoot || link.target === graphRoot)
      .map((link) => ({ ...link, isBranchLink: true }));
    const directNodeIds = new Set<string>([graphRoot]);
    directLinks.forEach((link) => {
      directNodeIds.add(link.source as string);
      directNodeIds.add(link.target as string);
    });
    const directNodes: GraphNode[] = graphData.nodes
      .filter((node) => directNodeIds.has(node.id))
      .map((node) => ({
        ...node,
        level: node.isRoot ? 0 as const : 2 as const,
      }));
    const rootNode = directNodes.find((node) => node.isRoot);

    // Department browsing stays in its original CMeKG-like direct layout.
    // Disease browsing gets one compact, unlabeled junction per relation
    // colour, so all entities of the same colour meet before the centre.
    if (rootNode?.type === 'Department') {
      return { nodes: directNodes, links: directLinks };
    }

    const branchNodes = [...directNodes];
    const branchLinks: GraphLink[] = [];
    const branchAnchors = new Map<string, GraphNode>();

    const ensureBranchAnchor = (relation: string) => {
      const existing = branchAnchors.get(relation);
      if (existing) return existing;
      const anchor: GraphNode = {
        id: relationHubId(relation),
        name: '',
        type: 'RelationHub',
        relation,
        isBranchHub: true,
        isBranchAnchor: true,
        level: 1,
        val: 0.01,
        color: getRelationConfig(relation).color,
      };
      branchAnchors.set(relation, anchor);
      branchNodes.push(anchor);
      branchLinks.push({
        source: graphRoot,
        target: anchor.id,
        relation,
        color: getRelationConfig(relation).color,
        label: getRelationConfig(relation).label,
        isBranchLink: true,
        isBranchStem: true,
      });
      return anchor;
    };

    directLinks.forEach((link) => {
      const source = endpointName(link.source);
      const target = endpointName(link.target);
      const direct = source === graphRoot || target === graphRoot;
      if (!direct) {
        branchLinks.push({ ...link, source, target });
        return;
      }
      const anchor = ensureBranchAnchor(link.relation);
      const other = source === graphRoot ? target : source;
      branchLinks.push({
        ...link,
        source: anchor.id,
        target: other,
        color: getRelationConfig(link.relation).color,
        label: getRelationConfig(link.relation).label,
        isBranchLink: true,
      });
    });
    return { nodes: branchNodes, links: branchLinks };

  }, [graphData, graphRoot]);

  useEffect(() => {
    setHoveredNodeId(null);
    setCollapsedRelations(new Set());
  }, [graphData.nodes]);

  useEffect(() => {
    const element = chartAreaRef.current;
    if (!element) return;
    const updateSize = () => {
      const { width, height } = element.getBoundingClientRect();
      setGraphSize({ width: Math.floor(width), height: Math.floor(height) });
    };
    updateSize();
    const observer = new ResizeObserver(updateSize);
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    let cancelled = false;
    const loadDepartments = async () => {
      try {
        const resp = await fetch(`${API_BASE}/api/v1/kg/departments`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!resp.ok) return;
        const data: { departments?: unknown } = await resp.json();
        if (!Array.isArray(data.departments) || data.departments.length === 0 || cancelled) return;
        const names = data.departments.filter((name): name is string => typeof name === 'string');
        setDepartmentTags(names.map((name, index) => ({
          name,
          color: DEPT_TAGS[index % DEPT_TAGS.length]?.color || '#178c9f',
        })));
      } catch {
        // Keep the six offline shortcuts when the graph service is unavailable.
      }
    };
    void loadDepartments();
    return () => { cancelled = true; };
  }, [accessToken]);

  const toGraphData = useCallback((data: GraphData, rootName: string) => {
    const nodeRelations = new Map<string, string>();
    data.links.forEach((l) => {
      if (l.source === rootName) nodeRelations.set(l.target, relationKey(l.rel_type, l.target));
      if (l.target === rootName) nodeRelations.set(l.source, relationKey(l.rel_type, l.source));
    });
    data.links.forEach((l) => {
      if (l.source !== rootName && !nodeRelations.has(l.source)) nodeRelations.set(l.source, relationKey(l.rel_type, l.source));
      if (l.target !== rootName && !nodeRelations.has(l.target)) nodeRelations.set(l.target, relationKey(l.rel_type, l.target));
    });

    const nodes: GraphNode[] = data.nodes.map((n) => {
      const relation = nodeRelations.get(n.name) || 'related';
      const isRoot = n.name === rootName;
      return {
        id: n.name,
        name: n.name,
        type: n.type,
        desc: n.desc,
        diseaseCount: n.diseaseCount,
        publishedDiseaseCount: n.publishedDiseaseCount,
        referenceDiseaseCount: n.referenceDiseaseCount,
        knowledgeStatus: n.knowledgeStatus,
        relation,
        isRoot,
        ...(isRoot ? { fx: 0, fy: 0, fz: 0 } : {}),
        val: isRoot ? 10 : 0.5,
        color: isRoot ? '#63c4c7' : getRelationConfig(relation).color,
      };
    });

    const nodeNames = new Set(nodes.map((node) => node.id));
    const links: GraphLink[] = data.links
      .filter((link) => nodeNames.has(link.source) && nodeNames.has(link.target))
      .map((l) => ({
        source: l.source,
        target: l.target,
        rel_type: l.rel_type,
        relation: relationKey(l.rel_type, l.source === rootName ? l.target : l.source),
        color: getRelationConfig(relationKey(l.rel_type, l.source === rootName ? l.target : l.source)).color,
        evidence: l.evidence,
      }));

    return { nodes, links };
  }, []);

  const loadOverview = useCallback(async () => {
    setLoading(true);
    setGraphError('');
    try {
      const resp = await fetch(`${API_BASE}/api/v1/kg/overview`, {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      if (!resp.ok) throw new Error(`总览图谱请求失败（HTTP ${resp.status}）`);
      const data = await resp.json();
      const nextGraphData = toGraphData(data, '医学知识库');
      setActivePerspective('overview');
      setViewMode('graph');
      setGraphRoot('医学知识库');
      setSelectedNode(null);
      setVisibleRelations(new Set(RELATION_KEYS));
      setShowSecondaryLinks(false);
      setShownNodeCounts({});
      setGraphData(nextGraphData);
      setSearchResults([]);
      setSearchQuery('');
      setNodeCount(nextGraphData.nodes.length);
      setLinkCount(nextGraphData.links.length);
    } catch (e) {
      console.error('Failed to load graph overview:', e);
      setGraphError(e instanceof Error ? e.message : '总览图谱加载失败');
    } finally {
      setLoading(false);
    }
  }, [accessToken, toGraphData]);

  // Load graph
  const loadGraph = useCallback(
    async (name: string) => {
      setLoading(true);
      setGraphError('');
      try {
        const resp = await fetch(`${API_BASE}/api/v1/kg/graph?name=${encodeURIComponent(name)}&depth=1`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!resp.ok) throw new Error(`图谱请求失败（HTTP ${resp.status}）`);
        const data = await resp.json();
        const nextGraphData = toGraphData(data, name);
        setActivePerspective('clinical');
        setGraphRoot(name);
        setSelectedNode(null);
        setVisibleRelations(new Set(RELATION_KEYS));
        setShowSecondaryLinks(false);
        setShownNodeCounts({});
        setGraphData(nextGraphData);
        setSearchResults([]);
        setSearchQuery(name);
        setNodeCount(nextGraphData.nodes.length);
        setLinkCount(nextGraphData.links.length);
      } catch (e) {
        console.error('Failed to load graph:', e);
        setGraphError(e instanceof Error ? e.message : '图谱加载失败');
      } finally {
        setLoading(false);
      }
    },
    [accessToken, toGraphData],
  );

  // Search
  const handleSearch = useCallback(
    async (value: string) => {
      const q = value.trim();
      if (!q) { setSearchResults([]); return; }
      setLoading(true);
      setGraphError('');
      try {
        const resp = await fetch(`${API_BASE}/api/v1/kg/search?q=${encodeURIComponent(q)}&limit=12`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!resp.ok) throw new Error(`搜索请求失败（HTTP ${resp.status}）`);
        const data = await resp.json();
        setSearchResults(data.results || []);
      } catch (e) {
        setSearchResults([]);
        setGraphError(e instanceof Error ? e.message : '搜索暂时不可用');
      } finally {
        setLoading(false);
      }
    },
    [accessToken],
  );

  // Load entire department
  const loadDepartment = useCallback(
    async (deptName: string) => {
      setLoading(true);
      try {
        const resp = await fetch(`${API_BASE}/api/v1/kg/department?name=${encodeURIComponent(deptName)}&limit=200`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!resp.ok) throw new Error(`科室图谱请求失败（HTTP ${resp.status}）`);
        const data = await resp.json();
        const nextGraphData = toGraphData(data, deptName);
        setActivePerspective('clinical');
        setGraphRoot(deptName);
        setSelectedNode(null);
        setVisibleRelations(new Set(RELATION_KEYS));
        setShowSecondaryLinks(false);
        setShownNodeCounts({});
        setGraphData(nextGraphData);
        setSearchResults([]);
        setSearchQuery(deptName);
        setNodeCount(nextGraphData.nodes.length);
        setLinkCount(nextGraphData.links.length);
      } catch (e) {
        console.error('Failed to load department:', e);
        setGraphError(e instanceof Error ? e.message : '科室图谱加载失败');
      } finally {
        setLoading(false);
      }
    },
    [accessToken, toGraphData],
  );

  const selectPerspective = (perspective: 'clinical' | 'overview') => {
    if (perspective === 'overview') {
      void loadOverview();
      return;
    }
    setActivePerspective('clinical');
    if (graphRoot === '医学知识库') {
      setGraphData({ nodes: [], links: [] });
      setGraphRoot('');
      setSelectedNode(null);
      setNodeCount(0);
      setLinkCount(0);
      setSearchQuery('');
    }
  };

  const handleNodeClick = useCallback((node: GraphNode) => {
    if (node.isBranchAnchor) return;
    if (node.isBranchHub) {
      setCollapsedRelations((current) => {
        const next = new Set(current);
        if (next.has(node.relation)) next.delete(node.relation);
        else next.add(node.relation);
        return next;
      });
      return;
    }
    const kgNode: KgNode = {
      name: node.name,
      type: node.type,
      desc: node.desc,
      knowledgeStatus: node.knowledgeStatus,
    };
    setSelectedNode(kgNode);
  }, []);

  const isEmpty = graphData.nodes.length === 0;
  const selectedLinks = selectedNode
    ? graphData.links.filter((link) =>
        endpointName(link.source) === selectedNode.name || endpointName(link.target) === selectedNode.name)
    : [];
  const selectedGraphNode = selectedNode
    ? graphData.nodes.find((node) => node.id === selectedNode.name)
    : undefined;
  const graphRootNode = graphData.nodes.find((node) => node.isRoot);
  const relationGroups = useMemo<RelationGroup[]>(() => {
    const nodesById = new Map(graphData.nodes.map((node) => [node.id, node]));
    const groupedNodes = new Map<string, Map<string, GraphNode>>();

    graphData.links.forEach((link) => {
      const source = endpointName(link.source);
      const target = endpointName(link.target);
      if (source !== graphRoot && target !== graphRoot) return;

      const otherName = source === graphRoot ? target : source;
      const otherNode = nodesById.get(otherName);
      if (!otherNode || otherNode.isRoot) return;
      const key = relationKey(link.rel_type, otherName);
      if (!groupedNodes.has(key)) groupedNodes.set(key, new Map());
      groupedNodes.get(key)?.set(otherNode.id, { ...otherNode, relation: key });
    });

    // The current APIs load direct neighbours. This fallback keeps the view
    // useful if a future response only supplies node-level relation metadata.
    if (groupedNodes.size === 0) {
      graphData.nodes
        .filter((node) => !node.isRoot)
        .forEach((node) => {
          if (!groupedNodes.has(node.relation)) groupedNodes.set(node.relation, new Map());
          groupedNodes.get(node.relation)?.set(node.id, node);
        });
    }

    return RELATION_KEYS
      .filter((key) => groupedNodes.has(key))
      .map((key) => ({ key, nodes: Array.from(groupedNodes.get(key)?.values() || []) }));
  }, [graphData, graphRoot]);
  const relationCounts = Object.fromEntries(relationGroups.map((group) => [group.key, group.nodes.length]));
  const activeRelationKeys = relationGroups.map((group) => group.key);
  const toggleRelation = (relation: string) => {
    setVisibleRelations((current) => {
      const next = new Set(current);
      if (next.has(relation)) next.delete(relation);
      else next.add(relation);
      return next;
    });
  };
  const toggleCollapsedRelation = (relation: string) => {
    setCollapsedRelations((current) => {
      const next = new Set(current);
      if (next.has(relation)) next.delete(relation);
      else next.add(relation);
      return next;
    });
  };
  const toggleGraphRelation = (relation: string) => {
    if (!visibleRelations.has(relation)) {
      setVisibleRelations((current) => new Set(current).add(relation));
      setCollapsedRelations((current) => {
        const next = new Set(current);
        next.delete(relation);
        return next;
      });
      return;
    }
    toggleCollapsedRelation(relation);
  };
  const relationshipLabel = (key: string) => {
    if (graphRootNode?.type === 'KnowledgeHub' && key === 'department') return '标准化科室';
    if (graphRootNode?.type !== 'Department') return getRelationConfig(key).label;
    if (key === 'department') return '本科室疾病';
    if (key === 'routing') return '初诊分流疾病';
    return getRelationConfig(key).label;
  };
  const revealMoreNodes = (key: string) => {
    setShownNodeCounts((current) => ({ ...current, [key]: (current[key] || 18) + 18 }));
  };
  const isDirectLink = (link: GraphLink) => {
    const source = endpointName(link.source);
    const target = endpointName(link.target);
    return source === graphRoot || target === graphRoot;
  };
  const directLinkCount = graphData.links.filter(isDirectLink).length;

  return (
    <div className="kg-container">
      <div className="kg-header">
        <div className="kg-header-left">
          <span className="kg-header-mark"><ApartmentOutlined /></span>
          <div>
            <span className="kg-header-kicker">Medical relationship index</span>
            <h2 className="kg-header-title">医学知识图谱</h2>
          </div>
          {!isEmpty && (
            <span className="kg-header-stats">
              <span><strong>{nodeCount}</strong> 节点</span>
              <span><strong>{linkCount}</strong> 关系</span>
            </span>
          )}
          {!isEmpty && (
            <div className="kg-view-switch" role="tablist" aria-label="图谱查看方式">
              <button
                className={viewMode === 'graph' ? 'kg-view-switch--active' : ''}
                role="tab"
                aria-selected={viewMode === 'graph'}
                onClick={() => setViewMode('graph')}
              >
                图谱
              </button>
              <button
                className={viewMode === 'outline' ? 'kg-view-switch--active' : ''}
                role="tab"
                aria-selected={viewMode === 'outline'}
                onClick={() => setViewMode('outline')}
              >
                梳理
              </button>
            </div>
          )}
        </div>
        <div className="kg-header-search">
          <Input.Search
            size="middle"
            placeholder="搜索疾病、症状、药物..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onSearch={handleSearch}
            loading={loading}
            allowClear
          />
          {searchResults.length > 0 && (
            <div className="kg-search-dropdown">
              {searchResults.map((r) => (
                <div
                  key={r.name}
                  className="kg-search-item"
                  onClick={() => void loadGraph(r.name)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter') void loadGraph(r.name); }}
                >
                  <span className="kg-search-dot" style={{ background: TYPE_COLORS[r.type] }} />
                  <span className="kg-search-name">{r.name}</span>
                  <Tag color={TYPE_COLORS[r.type]}>
                    {TYPE_LABELS[r.type] || r.type}
                  </Tag>
                  {r.knowledgeStatus === 'PUBLISHED' ? (
                    <Tag color="green">已审核</Tag>
                  ) : r.knowledgeStatus === 'STANDARDIZED' ? (
                    <Tag color="blue">标准科室</Tag>
                  ) : (
                    <Tag color="green">已审核知识</Tag>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <nav className="kg-perspectives" aria-label="医学知识图谱视角">
        <button
          className={`kg-perspective ${activePerspective === 'clinical' ? 'kg-perspective--active' : ''}`}
          aria-pressed={activePerspective === 'clinical'}
          onClick={() => selectPerspective('clinical')}
        >
          <span>CLINICAL LENS</span>
          <strong>临床探索</strong>
          <small>从疾病、症状、药物或检查进入局部关系图</small>
        </button>
        <button
          className={`kg-perspective ${activePerspective === 'overview' ? 'kg-perspective--active' : ''}`}
          aria-pressed={activePerspective === 'overview'}
          onClick={() => selectPerspective('overview')}
        >
          <span>DEPARTMENT LENS</span>
          <strong>科室总览</strong>
          <small>以标准化科室聚合知识范围，进入后再查看疾病</small>
        </button>
        {onOpenGovernance && (
          <button className="kg-perspective kg-perspective--governance" onClick={onOpenGovernance}>
            <span>GOVERNANCE</span>
            <strong>知识治理</strong>
            <small>维护和发布已审核医学知识</small>
          </button>
        )}
      </nav>

      <div className={`kg-body ${isIndexCollapsed ? 'kg-body--index-collapsed' : ''}`}>
        <aside className={`kg-index ${isIndexCollapsed ? 'kg-index--collapsed' : ''}`} aria-label="图谱探索索引">
          <div className="kg-index-section">
            <div className="kg-index-heading">
              <span>按科室浏览</span>
              <small>载入完整关系网</small>
            </div>
            <div className="kg-department-list">
              {departmentTags.map((department) => (
                <button key={department.name} onClick={() => void loadDepartment(department.name)}>
                  <span className="kg-department-swatch" style={{ background: department.color }} />
                  <span>{department.name}</span>
                  <span aria-hidden="true">→</span>
                </button>
              ))}
            </div>
          </div>
          <div className="kg-index-section kg-index-section--diseases">
            <div className="kg-index-heading">
              <span>常见疾病</span>
              <small>快速建立中心节点</small>
            </div>
            <div className="kg-disease-list">
              {QUICK_TAGS.map((name) => (
                <button key={name} onClick={() => { setSearchQuery(name); void loadGraph(name); }}>
                  {name}
                </button>
              ))}
            </div>
          </div>
          <div className="kg-index-note">
            <ThunderboltOutlined />
            <span>关系按临床语义分组展示；点击条目查看详情，选择“以此为中心”继续探索。</span>
          </div>
        </aside>
        <button
          type="button"
          className="kg-index-toggle"
          aria-label={isIndexCollapsed ? '展开左侧索引' : '收起左侧索引'}
          aria-expanded={!isIndexCollapsed}
          onClick={() => setIsIndexCollapsed((collapsed) => !collapsed)}
        >
          {isIndexCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        </button>

        <div className="kg-chart-area" ref={chartAreaRef}>
          {loading && (
            <div className="kg-loading">
              <Spin size="large" />
              <span>正在整理医学关系...</span>
            </div>
          )}

          {graphError && (
            <Alert
              className="kg-error"
              type="error"
              showIcon
              closable
              title="暂时无法读取知识图谱"
              description={graphError}
              onClose={() => setGraphError('')}
            />
          )}

          {!isEmpty ? (
            viewMode === 'graph' ? (
              <div className="kg-force-graph" aria-label={`${graphRoot}关系图谱`}>
                <CmekgForceGraph
                  data={visualGraphData}
                  width={graphSize.width}
                  height={graphSize.height}
                  layoutKey={graphRoot}
                  visibleRelations={visibleRelations}
                  collapsedRelations={collapsedRelations}
                  hoveredNodeId={hoveredNodeId}
                  selectedNodeId={selectedNode?.name}
                  showSecondaryLinks={showSecondaryLinks}
                  onNodeHover={(node) => setHoveredNodeId(node?.id || null)}
                  onNodeClick={handleNodeClick}
                  onBackgroundClick={() => {
                    setSelectedNode(null);
                    setHoveredNodeId(null);
                  }}
                />
                <div className="kg-legend" aria-label="关系类型筛选">
                  <div className="kg-legend-heading">
                    <span>{graphRoot} · 关系</span>
                    <button
                      onClick={() => {
                        setVisibleRelations(new Set(RELATION_KEYS));
                        setCollapsedRelations(new Set());
                      }}
                      disabled={
                        activeRelationKeys.every((key) => visibleRelations.has(key))
                        && collapsedRelations.size === 0
                      }
                    >
                      全部
                    </button>
                  </div>
                  {relationGroups.map((group) => {
                    const relation = getRelationConfig(group.key);
                    return (
                      <button
                        key={group.key}
                        className={`kg-legend-filter ${
                          visibleRelations.has(group.key) && !collapsedRelations.has(group.key)
                            ? 'kg-legend-filter--active'
                            : 'kg-legend-filter--collapsed'
                        }`}
                        aria-pressed={visibleRelations.has(group.key) && !collapsedRelations.has(group.key)}
                        aria-expanded={!collapsedRelations.has(group.key)}
                        onClick={() => toggleGraphRelation(group.key)}
                      >
                        <span className="kg-legend-dot" style={{ background: relation.color }} />
                        <span>{relationshipLabel(group.key)}</span>
                        <small>{relationCounts[group.key] || 0}</small>
                      </button>
                    );
                  })}
                  {linkCount > directLinkCount && (
                    <button className="kg-legend-secondary" onClick={() => setShowSecondaryLinks((current) => !current)}>
                      {showSecondaryLinks ? '隐藏次级关系线' : `显示次级关系线 · ${linkCount - directLinkCount}`}
                    </button>
                  )}
                </div>
              </div>
            ) : (
            <div className="kg-structured-map" aria-label={`${graphRoot}医学关系图谱`}>
              <section className="kg-root-stage" aria-label="中心概念">
                <div className="kg-root-card">
                  <span className="kg-root-kicker">CENTRAL CONCEPT</span>
                  <div className="kg-root-symbol" style={{ background: TYPE_COLORS[graphRootNode?.type || ''] || '#176e75' }}>
                    <MedicineBoxOutlined />
                  </div>
                  <strong>{graphRoot}</strong>
                  <span className="kg-root-type">{TYPE_LABELS[graphRootNode?.type || ''] || '医学概念'}</span>
                  <p>仅呈现与中心概念直接相连的一度关系；交叉关系不会自动叠加到当前视图。</p>
                  <div className="kg-root-statline">
                    <span><b>{relationGroups.length}</b> 类关系</span>
                    <span><b>{nodeCount - 1}</b> 个关联概念</span>
                  </div>
                </div>
              </section>

              <section className="kg-relationship-stage" aria-label="关系分组">
                <div className="kg-map-heading">
                  <div>
                    <span>一度关系视图</span>
                    <strong>按医学关系梳理</strong>
                  </div>
                  <small>点击关系筛选，条目按需展开</small>
                </div>

                <div className="kg-relation-filters" aria-label="关系筛选">
                  <button
                    className="kg-relation-filter kg-relation-filter--all"
                    onClick={() => setVisibleRelations(new Set(RELATION_KEYS))}
                    disabled={activeRelationKeys.every((key) => visibleRelations.has(key))}
                  >
                    显示全部
                  </button>
                  {relationGroups.map((group) => {
                    const relation = getRelationConfig(group.key);
                    return (
                      <button
                        key={group.key}
                        className={`kg-relation-filter ${visibleRelations.has(group.key) ? 'kg-relation-filter--active' : ''}`}
                        aria-pressed={visibleRelations.has(group.key)}
                        onClick={() => toggleRelation(group.key)}
                      >
                        <span style={{ background: relation.color }} />
                        {relationshipLabel(group.key)}
                        <small>{relationCounts[group.key] || 0}</small>
                      </button>
                    );
                  })}
                </div>

                <div className="kg-relationship-list">
                  {relationGroups
                    .filter((group) => visibleRelations.has(group.key))
                    .map((group) => {
                      const relation = getRelationConfig(group.key);
                      const visibleCount = shownNodeCounts[group.key] || 18;
                      const displayedNodes = group.nodes.slice(0, visibleCount);
                      const remaining = group.nodes.length - displayedNodes.length;
                      return (
                        <section className="kg-relation-group" key={group.key}>
                          <span className="kg-relation-connector" style={{ background: relation.color }} />
                          <div className="kg-relation-group-head">
                            <div>
                              <span className="kg-relation-group-dot" style={{ background: relation.color }} />
                              <strong>{relationshipLabel(group.key)}</strong>
                            </div>
                            <small>{group.nodes.length} 个关联概念</small>
                          </div>
                          <div className="kg-relation-node-grid">
                            {displayedNodes.map((node) => (
                              <button
                                key={`${group.key}-${node.id}`}
                                className={`kg-relation-node ${selectedNode?.name === node.name ? 'kg-relation-node--selected' : ''}`}
                                onClick={() => handleNodeClick(node)}
                              >
                                <span className="kg-relation-node-dot" style={{ background: TYPE_COLORS[node.type] || relation.color }} />
                                <span>{node.name}</span>
                                <small>{TYPE_LABELS[node.type] || node.type}</small>
                              </button>
                            ))}
                          </div>
                          {remaining > 0 && (
                            <button className="kg-relation-more" onClick={() => revealMoreNodes(group.key)}>
                              展开其余 {remaining} 个概念
                            </button>
                          )}
                        </section>
                      );
                    })}
                  {relationGroups.length > 0 && relationGroups.every((group) => !visibleRelations.has(group.key)) && (
                    <div className="kg-relationship-empty">当前已隐藏全部关系类别。可从上方重新选择要查看的类别。</div>
                  )}
                </div>
              </section>
            </div>
            )
          ) : !loading ? (
            <div className="kg-welcome">
              <div className="kg-welcome-icon">
                <MedicineBoxOutlined />
              </div>
              <span className="kg-welcome-kicker">关系画布</span>
              <h2>从一个医学概念开始</h2>
              <p>在左侧选择科室或疾病，或使用上方搜索框定位症状、药物与检查。</p>
            </div>
          ) : null}

        </div>

        {/* Detail panel */}
        {selectedNode && (
          <aside className="kg-detail" aria-label={`${selectedNode.name}详情`}>
            <div className="kg-detail-header">
              <div className="kg-detail-badge" style={{ background: selectedGraphNode?.color || TYPE_COLORS[selectedNode.type] }}>
                {selectedGraphNode?.isRoot ? '核' : getRelationConfig(selectedGraphNode?.relation).label.charAt(0)}
              </div>
              <div className="kg-detail-title">
                <strong>{selectedNode.name}</strong>
                <Tag color={TYPE_COLORS[selectedNode.type]}>
                  {TYPE_LABELS[selectedNode.type] || selectedNode.type}
                </Tag>
                {selectedNode.knowledgeStatus === 'PUBLISHED' ? (
                  <Tag color="green">已审核知识</Tag>
                ) : selectedNode.knowledgeStatus === 'STANDARDIZED' ? (
                  <Tag color="blue">标准科室</Tag>
                ) : (
                  <Tag color="green">已审核知识</Tag>
                )}
              </div>
              <button className="kg-detail-close" onClick={() => setSelectedNode(null)} aria-label="关闭详情">
                <CloseOutlined />
              </button>
            </div>

            {selectedNode.desc && (
              <div className="kg-detail-section">
                <div className="kg-detail-section-title">概述</div>
                <p className="kg-detail-desc">{selectedNode.desc}</p>
              </div>
            )}

            {selectedNode.name !== graphRoot && (
              <div className="kg-detail-section kg-detail-action-section">
                <div className="kg-detail-section-title">继续探索</div>
                <button
                  className="kg-detail-focus"
                  onClick={() => void (selectedNode.type === 'Department'
                    ? loadDepartment(selectedNode.name)
                    : loadGraph(selectedNode.name))}
                >
                  以“{selectedNode.name}”为中心梳理关系
                </button>
              </div>
            )}

            <div className="kg-detail-section">
              <div className="kg-detail-section-title" style={{ color: '#aaa' }}>
                关联关系
                <span className="kg-detail-count">{selectedLinks.length}</span>
              </div>
              <div className="kg-detail-links">
                {selectedLinks.map((l, i) => {
                    const source = endpointName(l.source);
                    const target = endpointName(l.target);
                    const other = source === selectedNode.name ? target : source;
                    const otherNode = graphData.nodes.find((n) => n.id === other);
                    const relation = getRelationConfig(l.relation);
                    return (
                      <div key={i} className="kg-detail-link" onClick={() => {
                        if (otherNode) {
                          setSelectedNode({
                            name: otherNode.name,
                            type: otherNode.type,
                            desc: otherNode.desc,
                            knowledgeStatus: otherNode.knowledgeStatus,
                          });
                        }
                      }}>
                        <span className="kg-detail-rel" style={{ background: `${relation.color}18`, color: relation.color }}>
                          {relation.label}
                        </span>
                        <span className="kg-detail-other">{other}</span>
                      </div>
                    );
                  })}
              </div>
            </div>
          </aside>
        )}
      </div>
    </div>
  );
}
