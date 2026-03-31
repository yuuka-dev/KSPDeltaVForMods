/**
 * useRouteMap - D3.js force-directed route map composable.
 *
 * Separates D3 rendering lifecycle from Vue reactivity.
 * The component provides the SVG container ref; this composable owns the simulation.
 */

import * as d3 from 'd3'
import { onUnmounted } from 'vue'
import type { Ref } from 'vue'
import type { BodySummary, BodyTreeNode, DestinationEntry, DvStepResponse } from '@/types/api'

// --- Interfaces ---

export interface MapNode extends d3.SimulationNodeDatum {
  id: string
  name: string
  displayName: string
  hasAtmosphere: boolean
  isHomeWorld: boolean
  isStar: boolean
  children: string[]
}

export interface MapLink extends d3.SimulationLinkDatum<MapNode> {
  dv: number
}

export interface UseRouteMapOptions {
  onNodeClick?: (name: string) => void
}

// --- Color scheme ---

const COLOR_STAR = '#f59e0b'
const COLOR_HOME = '#22c55e'
const COLOR_ATMO = '#3b82f6'
const COLOR_AIRLESS = '#6b7280'
const COLOR_ROUTE = '#ef4444'

const NODE_SIZE_STAR = 16
const NODE_SIZE_HOME = 12
const NODE_SIZE_DEFAULT = 8

function nodeColor(node: MapNode): string {
  if (node.isStar) return COLOR_STAR
  if (node.isHomeWorld) return COLOR_HOME
  if (node.hasAtmosphere) return COLOR_ATMO
  return COLOR_AIRLESS
}

function nodeRadius(node: MapNode): number {
  if (node.isStar) return NODE_SIZE_STAR
  if (node.isHomeWorld) return NODE_SIZE_HOME
  return NODE_SIZE_DEFAULT
}

// --- Tree traversal ---

/**
 * Recursively traverse BodyTreeNode[] and build flat nodes/links arrays.
 *
 * @param tree - The tree structure from SystemResponse.
 * @param root - The root BodySummary (the star).
 * @param homeWorldName - Name of the home world for color differentiation.
 * @param destinations - Flat DestinationEntry[] for ΔV labels on links.
 */
export function buildNodes(
  tree: BodyTreeNode[],
  root: BodySummary,
  homeWorldName: string,
  destinations: DestinationEntry[],
): { nodes: MapNode[]; links: MapLink[] } {
  const nodes: MapNode[] = []
  const links: MapLink[] = []

  const dvMap = new Map<string, number>()
  const atmosphereMap = new Map<string, boolean>()
  for (const entry of destinations) {
    dvMap.set(entry.body.name, entry.transfer_dv)
    atmosphereMap.set(entry.body.name, entry.body.has_atmosphere)
  }

  // Insert the root star node
  nodes.push({
    id: root.name,
    name: root.name,
    displayName: root.display_name,
    hasAtmosphere: root.has_atmosphere,
    isHomeWorld: root.name === homeWorldName,
    isStar: true,
    children: tree.map((n) => n.name),
  })

  function traverse(nodeList: BodyTreeNode[], parentName: string): void {
    for (const treeNode of nodeList) {
      const isStar = parentName === '' // Only the root is a star; handled above
      nodes.push({
        id: treeNode.name,
        name: treeNode.name,
        displayName: treeNode.display_name,
        hasAtmosphere: atmosphereMap.get(treeNode.name) ?? false,
        isHomeWorld: treeNode.name === homeWorldName,
        isStar,
        children: treeNode.children.map((c) => c.name),
      })

      links.push({
        source: parentName,
        target: treeNode.name,
        dv: dvMap.get(treeNode.name) ?? 0,
      })

      if (treeNode.children.length > 0) {
        traverse(treeNode.children, treeNode.name)
      }
    }
  }

  traverse(tree, root.name)
  return { nodes, links }
}

// --- Composable ---

export function useRouteMap(
  containerRef: Ref<HTMLElement | null>,
  options: UseRouteMapOptions = {},
) {
  let simulation: d3.Simulation<MapNode, MapLink> | null = null
  let svgEl: SVGSVGElement | null = null
  let linkSelection: d3.Selection<SVGLineElement, MapLink, SVGGElement, unknown> | null = null
  let currentNodes: MapNode[] = []

  /**
   * Clear the previous SVG, build fresh simulation & render.
   *
   * @param tree - BodyTreeNode[] from SystemResponse.
   * @param root - Root BodySummary.
   * @param homeWorldName - Name of the home world.
   * @param destinations - DestinationEntry[] for edge labels.
   */
  function render(
    tree: BodyTreeNode[],
    root: BodySummary,
    homeWorldName: string,
    destinations: DestinationEntry[],
  ): void {
    const container = containerRef.value
    if (!container) return

    // Clear
    destroy()

    const width = container.clientWidth || 800
    const height = container.clientHeight || 500

    const { nodes, links } = buildNodes(tree, root, homeWorldName, destinations)
    currentNodes = nodes

    // Create SVG
    const svg = d3
      .select(container)
      .append('svg')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('viewBox', `0 0 ${width} ${height}`)
      .style('display', 'block')

    svgEl = svg.node()

    // Zoom / pan layer
    const zoomG = svg.append('g').attr('class', 'zoom-layer')

    const zoom = d3
      .zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 5])
      .on('zoom', (event: d3.D3ZoomEvent<SVGSVGElement, unknown>) => {
        zoomG.attr('transform', event.transform.toString())
      })

    svg.call(zoom)

    // Layers inside zoom group
    const linkG = zoomG.append('g').attr('class', 'links')
    const linkLabelG = zoomG.append('g').attr('class', 'link-labels')
    const nodeG = zoomG.append('g').attr('class', 'nodes')

    // Draw links
    linkSelection = linkG
      .selectAll<SVGLineElement, MapLink>('line')
      .data(links)
      .join('line')
      .attr('stroke', '#4b5563')
      .attr('stroke-width', 1.5)
      .attr('stroke-opacity', 0.7)

    // Link labels
    const linkLabels = linkLabelG
      .selectAll<SVGTextElement, MapLink>('text')
      .data(links.filter((l) => l.dv > 0))
      .join('text')
      .attr('font-size', 9)
      .attr('fill', '#9ca3af')
      .attr('text-anchor', 'middle')
      .attr('dy', '-3')
      .text((d) => `${Math.round(d.dv)} m/s`)

    // Draw nodes
    const nodeCircles = nodeG
      .selectAll<SVGCircleElement, MapNode>('circle')
      .data(nodes)
      .join('circle')
      .attr('r', nodeRadius)
      .attr('fill', nodeColor)
      .attr('stroke', '#1f2937')
      .attr('stroke-width', 1.5)
      .attr('cursor', 'pointer')

    // Tooltips
    nodeCircles.append('title').text((d) => d.displayName)

    // Node labels
    nodeG
      .selectAll<SVGTextElement, MapNode>('text')
      .data(nodes)
      .join('text')
      .attr('font-size', 10)
      .attr('fill', '#e5e7eb')
      .attr('text-anchor', 'middle')
      .attr('dy', (d) => nodeRadius(d) + 12)
      .text((d) => d.displayName)
      .attr('pointer-events', 'none')

    // Click handler
    nodeCircles.on('click', (_event: MouseEvent, d: MapNode) => {
      options.onNodeClick?.(d.name)
    })

    // Drag
    const drag = d3
      .drag<SVGCircleElement, MapNode>()
      .on('start', (event: d3.D3DragEvent<SVGCircleElement, MapNode, MapNode>, d: MapNode) => {
        if (!event.active) simulation?.alphaTarget(0.3).restart()
        d.fx = d.x
        d.fy = d.y
      })
      .on('drag', (event: d3.D3DragEvent<SVGCircleElement, MapNode, MapNode>, d: MapNode) => {
        d.fx = event.x
        d.fy = event.y
      })
      .on('end', (event: d3.D3DragEvent<SVGCircleElement, MapNode, MapNode>, d: MapNode) => {
        if (!event.active) simulation?.alphaTarget(0)
        d.fx = null
        d.fy = null
      })

    nodeCircles.call(drag)

    // Force simulation
    simulation = d3
      .forceSimulation<MapNode, MapLink>(nodes)
      .force(
        'link',
        d3
          .forceLink<MapNode, MapLink>(links)
          .id((d) => d.id)
          .distance(100),
      )
      .force('charge', d3.forceManyBody<MapNode>().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .on('tick', () => {
        linkSelection
          ?.attr('x1', (d) => (d.source as MapNode).x ?? 0)
          .attr('y1', (d) => (d.source as MapNode).y ?? 0)
          .attr('x2', (d) => (d.target as MapNode).x ?? 0)
          .attr('y2', (d) => (d.target as MapNode).y ?? 0)

        linkLabels
          .attr(
            'x',
            (d) => (((d.source as MapNode).x ?? 0) + ((d.target as MapNode).x ?? 0)) / 2,
          )
          .attr(
            'y',
            (d) => (((d.source as MapNode).y ?? 0) + ((d.target as MapNode).y ?? 0)) / 2,
          )

        nodeCircles.attr('cx', (d) => d.x ?? 0).attr('cy', (d) => d.y ?? 0)

        nodeG
          .selectAll<SVGTextElement, MapNode>('text')
          .attr('x', (d) => d.x ?? 0)
          .attr('y', (d) => d.y ?? 0)
      })
  }

  /**
   * Highlight route edges in red based on matching step labels.
   *
   * @param steps - DvStepResponse[] from RouteResponse.
   */
  function highlightRoute(steps: DvStepResponse[]): void {
    if (!linkSelection) return

    // Build set of body names mentioned in route steps
    const mentionedBodies = new Set<string>()
    for (const step of steps) {
      for (const node of currentNodes) {
        if (step.label.includes(node.id)) {
          mentionedBodies.add(node.id)
        }
      }
    }

    linkSelection
      .attr('stroke', (d: MapLink) => {
        const targetId = typeof d.target === 'object' ? (d.target as MapNode).id : String(d.target)
        return mentionedBodies.has(targetId) ? COLOR_ROUTE : '#4b5563'
      })
      .attr('stroke-width', (d: MapLink) => {
        const targetId = typeof d.target === 'object' ? (d.target as MapNode).id : String(d.target)
        return mentionedBodies.has(targetId) ? 4 : 2
      })
  }

  /**
   * Stop the simulation and remove the SVG element.
   * Must be called on unmount.
   */
  function destroy(): void {
    simulation?.stop()
    simulation = null
    linkSelection = null
    currentNodes = []
    if (svgEl) {
      svgEl.remove()
      svgEl = null
    }
  }

  onUnmounted(() => {
    destroy()
  })

  return { render, highlightRoute, destroy }
}
