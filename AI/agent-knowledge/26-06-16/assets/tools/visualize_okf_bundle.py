#!/usr/bin/env python3
"""Generate an OKF bundle visualization.

This is a project-level helper, not an OKF protocol requirement.

Modes:
- auto: try the official `enrichment_agent visualize` first, then fall back to
  the local extended viewer.
- official: call only the official visualizer and fail if unavailable.
- extended: generate a local HTML viewer with official-style Cytoscape/marked
  visualization plus project additions.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from okf_bundle_common import OKFDocumentData, parse_log, safe_string, scan_bundle

PALETTE = [
    "#4f46e5",
    "#0891b2",
    "#16a34a",
    "#ca8a04",
    "#dc2626",
    "#9333ea",
    "#0f766e",
    "#be185d",
    "#475569",
    "#ea580c",
]


def official_command(bundle: Path, output: Path, name: str) -> list[str]:
    return [sys.executable, "-m", "enrichment_agent", "visualize", "--bundle", str(bundle), "--out", str(output), "--name", name]


def run_official_visualizer(bundle: Path, output: Path, name: str) -> tuple[bool, str]:
    command = official_command(bundle, output, name)
    try:
        completed = subprocess.run(command, check=False, text=True, capture_output=True)
    except OSError as exc:
        return False, f"failed to start official visualizer: {exc}"
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        return False, f"official visualizer failed with exit code {completed.returncode}: {detail}"
    return True, (completed.stderr or completed.stdout or "official visualizer completed").strip()


def normalize_tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def jsonable(value: Any) -> Any:
    try:
        json.dumps(value, ensure_ascii=False)
        return value
    except TypeError:
        if isinstance(value, dict):
            return {str(key): jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [jsonable(item) for item in value]
        return safe_string(value)


def concept_docs(docs: list[OKFDocumentData]) -> list[OKFDocumentData]:
    return [doc for doc in docs if not doc.is_reserved]


def collect_bundle_data(root: Path, name: str) -> dict[str, Any]:
    docs = scan_bundle(root)
    concepts = concept_docs(docs)
    types = sorted({doc.type or "Concept" for doc in concepts})
    colors = {concept_type: PALETTE[index % len(PALETTE)] for index, concept_type in enumerate(types)}

    known_ids = {doc.id for doc in concepts if doc.id}
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str]] = set()
    broken_links: list[dict[str, Any]] = []
    external_links: list[dict[str, Any]] = []

    for doc in concepts:
        concept_type = doc.type or "Concept"
        tags = normalize_tags(doc.tags)
        node_id = doc.id or doc.path.stem
        body_size = len(doc.body or "")
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "label": doc.title or node_id,
                    "type": concept_type,
                    "description": doc.description,
                    "resource": jsonable(doc.resource),
                    "tags": tags,
                    "color": colors.get(concept_type, "#64748b"),
                    "size": 30 + min(50, body_size // 280),
                    "timestamp": safe_string(doc.timestamp),
                    "frontmatter": jsonable(doc.frontmatter),
                    "body": doc.body,
                    "citations": [citation.__dict__ for citation in doc.citations],
                    "path": doc.rel_path,
                }
            }
        )

    for doc in concepts:
        if not doc.id:
            continue
        for link in doc.links:
            if link.is_external:
                external_links.append({"source": doc.id, "label": link.label, "target": link.target_raw})
                continue
            if not link.is_internal_markdown:
                continue
            if link.exists and link.target_id in known_ids and link.target_id != doc.id:
                edge_key = (doc.id, link.target_id)
                if edge_key not in seen_edges:
                    seen_edges.add(edge_key)
                    edges.append(
                        {
                            "data": {
                                "id": f"{doc.id}__{link.target_id}",
                                "source": doc.id,
                                "target": link.target_id,
                                "label": link.label,
                                "raw": link.target_raw,
                            }
                        }
                    )
            else:
                broken_links.append(
                    {
                        "source": doc.id,
                        "sourcePath": doc.rel_path,
                        "label": link.label,
                        "target": link.target_raw,
                        "resolvedId": link.target_id,
                        "reason": "outside bundle" if link.outside_bundle else "missing target or non-concept target",
                    }
                )

    logs: list[dict[str, Any]] = []
    for doc in docs:
        if doc.reserved_name == "log.md":
            text = doc.path.read_text(encoding="utf-8")
            logs.extend({"path": doc.rel_path, "date": group.date, "entries": group.entries} for group in parse_log(text))

    index_links: list[dict[str, Any]] = []
    for doc in docs:
        if doc.reserved_name == "index.md":
            for link in doc.links:
                if link.is_internal_markdown:
                    index_links.append(
                        {
                            "source": doc.rel_path,
                            "label": link.label,
                            "target": link.target_raw,
                            "targetId": link.target_id,
                            "exists": link.exists,
                        }
                    )

    return {
        "name": name,
        "nodes": nodes,
        "edges": edges,
        "types": types,
        "colors": colors,
        "bodies": {node["data"]["id"]: node["data"].get("body", "") for node in nodes},
        "brokenLinks": broken_links,
        "externalLinks": external_links,
        "logs": logs,
        "indexLinks": index_links,
        "meta": {
            "nodeCount": len(nodes),
            "edgeCount": len(edges),
            "brokenLinkCount": len(broken_links),
            "note": "Local extended viewer using the same Cytoscape.js and marked libraries as the official OKF viewer.",
        },
    }


def render_html(bundle_data: dict[str, Any]) -> str:
    data_json = json.dumps(bundle_data, ensure_ascii=False)
    return HTML_TEMPLATE.replace("__BUNDLE_DATA__", data_json)


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>OKF Bundle Visualization</title>
<script src="https://cdn.jsdelivr.net/npm/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js"></script>
<style>
* { box-sizing: border-box; }
:root { --ink:#e5e7eb; --muted:#94a3b8; --panel:#ffffff; --line:#dbe3ef; --accent:#7c3aed; --accent-2:#06b6d4; --slate:#0f172a; }
body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,sans-serif; font-size:14px; color:#e5e7eb; background:linear-gradient(135deg,#0f172a 0%,#1e1b4b 48%,#0e7490 100%); display:flex; flex-direction:column; height:100vh; }
header { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:12px 18px; background:linear-gradient(135deg,rgba(15,23,42,.96),rgba(49,46,129,.94)); color:#fff; border-bottom:1px solid rgba(255,255,255,.12); box-shadow:0 10px 30px rgba(15,23,42,.24); flex-shrink:0; }
.title strong { font-size:16px; margin-right:8px; letter-spacing:.2px; }
.muted { color:#64748b; font-size:12px; }
header .muted { color:#cbd5e1; }
.controls { display:flex; gap:8px; flex-wrap:wrap; }
.controls input,.controls select,.controls button { font-size:13px; padding:6px 9px; border:1px solid rgba(255,255,255,.22); border-radius:8px; color:#e5e7eb; background:rgba(15,23,42,.42); outline:none; }
.controls input { width:min(400px, 36vw); }
.controls input::placeholder { color:#a5b4fc; }
.controls select option { color:#0f172a; background:#fff; }
.controls button { cursor:pointer; background:linear-gradient(135deg,var(--accent),var(--accent-2)); border-color:transparent; color:#fff; font-weight:600; }
.controls button:hover { filter:brightness(1.08); }
main { display:flex; flex:1; min-height:0; padding:14px; gap:14px; }
#graph-wrap { flex:1 1 60%; position:relative; min-width:0; overflow:hidden; background:radial-gradient(circle at 24% 18%,rgba(124,58,237,.20),transparent 30%),radial-gradient(circle at 76% 72%,rgba(6,182,212,.18),transparent 35%),#f8fafc; border:1px solid rgba(255,255,255,.35); border-radius:18px; box-shadow:0 18px 45px rgba(15,23,42,.22); }
#graph { position:absolute; inset:0; }
#stats { position:absolute; right:14px; top:14px; background:rgba(15,23,42,.82); border:1px solid rgba(255,255,255,.16); border-radius:999px; padding:7px 11px; color:#e5e7eb; font-size:12px; z-index:2; box-shadow:0 10px 24px rgba(15,23,42,.20); }
#detail { flex:0 0 40%; overflow-y:auto; padding:20px 24px; color:#0f172a; background:rgba(255,255,255,.96); border:1px solid rgba(255,255,255,.52); border-radius:18px; box-shadow:0 18px 45px rgba(15,23,42,.20); }
#detail-empty { text-align:center; margin-top:40px; }
.tabs { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:14px; }
.tab { border:1px solid #d7deea; background:#f8fafc; border-radius:999px; padding:5px 11px; cursor:pointer; color:#475569; font-weight:700; }
.tab.active { background:linear-gradient(135deg,var(--accent),var(--accent-2)); color:#fff; border-color:transparent; box-shadow:0 8px 18px rgba(79,70,229,.20); }
.type-chip,.tag { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; color:#fff; background:#94a3b8; margin:0 4px 4px 0; }
.tag { color:#475569; background:#eef2ff; border:1px solid #e0e7ff; border-radius:999px; font-weight:500; }
.detail-header { margin-bottom:14px; padding:13px 14px; border-radius:14px; background:linear-gradient(135deg,#0f172a,#312e81); color:#fff; box-shadow:0 10px 24px rgba(15,23,42,.16); }
.detail-header h1 { font-size:19px; margin:6px 0 2px; font-weight:700; color:#fff; }
.detail-header .muted { color:#cbd5e1; font-size:13px; font-weight:600; }
.detail-header .type-chip { border:1px solid rgba(255,255,255,.26); }
dl.frontmatter { display:grid; grid-template-columns:90px 1fr; row-gap:5px; column-gap:12px; margin:10px 0 14px; font-size:13px; }
dl.frontmatter dt { color:#64748b; font-weight:600; }
dl.frontmatter dd { margin:0; word-break:break-word; }
a { color:#4f46e5; }
hr { border:none; border-top:1px solid var(--line); margin:14px 0; }
pre { background:#111827; color:#e5e7eb; padding:11px 13px; border-radius:10px; overflow:auto; font-size:12px; white-space:pre-wrap; }
.card { border:1px solid #dbe3ef; border-radius:12px; padding:11px; margin:9px 0; color:#0f172a; background:linear-gradient(180deg,#ffffff,#f8fafc); box-shadow:0 5px 16px rgba(15,23,42,.05); }
#detail-body { font-size:13px; line-height:1.58; color:#1f2937; }
#detail-body h1 { font-size:16px; margin:18px 0 6px; padding-bottom:5px; border-bottom:1px solid var(--line); color:#1e1b4b; }
#detail-body h2 { font-size:14px; margin:14px 0 4px; color:#334155; }
#detail-body h3 { font-size:13px; margin:12px 0 4px; color:#475569; }
#detail-body p { margin:6px 0; }
#detail-body code { background:#eef2ff; color:#3730a3; padding:1px 4px; border-radius:4px; font-size:12px; font-family:ui-monospace,"SF Mono",Consolas,monospace; }
#detail-body pre code { background:transparent; color:inherit; padding:0; }
#detail-body ul,#detail-body ol { padding-left:22px; margin:6px 0; }
#detail-body table { border-collapse:collapse; margin:8px 0; }
#detail-body th,#detail-body td { border:1px solid #dbe3ef; padding:4px 8px; font-size:12px; }
#missing-lib { display:none; padding:16px; color:#991b1b; background:#fee2e2; border-bottom:1px solid #fecaca; }
</style>
</head>
<body>
<div id="missing-lib">未能加载 Cytoscape.js 或 marked。请检查网络/CDN，或改用官方已生成文件。</div>
<header>
  <div class="title"><strong id="bundle-name"></strong><span class="muted">OKF bundle · local extended viewer</span></div>
  <div class="controls">
    <input id="search" type="search" placeholder="Search title / id / description / tag / body">
    <select id="filter-type"><option value="">All types</option></select>
    <select id="layout"><option value="cose">cose (force)</option><option value="concentric">concentric</option><option value="breadthfirst">breadth-first</option><option value="circle">circle</option><option value="grid">grid</option></select>
    <button id="reset">Reset view</button>
  </div>
</header>
<main>
  <section id="graph-wrap"><section id="graph"></section><div id="stats"></div></section>
  <section id="detail"><div id="detail-empty" class="muted">Click a node to see its details.</div><article id="detail-content" hidden></article></section>
</main>
<script>
window.BUNDLE = __BUNDLE_DATA__;
(function () {
  const bundle = window.BUNDLE;
  document.title = `${bundle.name} — OKF Viewer`;
  document.getElementById('bundle-name').textContent = bundle.name;
  if (!window.cytoscape || !window.marked) {
    document.getElementById('missing-lib').style.display = 'block';
    return;
  }

  const typeSelect = document.getElementById('filter-type');
  for (const t of bundle.types) {
    const opt = document.createElement('option');
    opt.value = t; opt.textContent = t; typeSelect.appendChild(opt);
  }

  const nodeIndex = {};
  for (const n of bundle.nodes) nodeIndex[n.data.id] = n.data;
  const backlinks = {};
  for (const edge of bundle.edges) {
    const {source, target} = edge.data;
    (backlinks[target] ||= []).push(source);
  }

  const cy = cytoscape({
    container: document.getElementById('graph'),
    elements: [...bundle.nodes, ...bundle.edges],
    style: [
      { selector: 'node', style: {
        'background-color': 'data(color)', 'label': 'data(label)', 'color': '#0f172a',
        'font-size': 9, 'font-weight': 650, 'text-valign': 'bottom', 'text-margin-y': 4, 'text-wrap': 'wrap',
        'text-max-width': 96, 'text-outline-width': 0,
        'width': 'data(size)', 'height': 'data(size)',
        'border-width': 1, 'border-color': 'rgba(255,255,255,.72)'
      }},
      { selector: 'node:selected', style: {'border-width': 3, 'border-color': '#f59e0b'} },
      { selector: 'edge', style: {
        'width': 1.4, 'line-color': 'rgba(100,116,139,.30)', 'target-arrow-color': 'rgba(100,116,139,.34)',
        'target-arrow-shape': 'triangle', 'curve-style': 'bezier', 'arrow-scale': .82
      }},
      { selector: 'edge:selected', style: {'line-color': '#f59e0b', 'target-arrow-color': '#f59e0b', 'width': 2.5} },
      { selector: '.dim', style: {'opacity': .15} }
    ],
    layout: { name: 'cose', animate: false, padding: 50 },
    wheelSensitivity: .2
  });

  const stats = document.getElementById('stats');
  function updateStats() {
    const visible = cy.nodes().filter(n => !n.hasClass('dim')).length;
    stats.textContent = `${visible}/${bundle.meta.nodeCount} concepts · ${bundle.meta.edgeCount} links · ${bundle.meta.brokenLinkCount} broken`;
  }
  updateStats();

  cy.on('tap', 'node', evt => showDetail(evt.target.id(), 'detail'));
  cy.on('tap', evt => { if (evt.target === cy) clearSelection(); });

  document.getElementById('layout').addEventListener('change', e => {
    cy.layout({ name: e.target.value, animate: false, padding: 50 }).run();
  });
  document.getElementById('reset').addEventListener('click', () => { cy.fit(null, 50); clearSelection(); });
  document.getElementById('search').addEventListener('input', applyFilters);
  document.getElementById('filter-type').addEventListener('change', applyFilters);

  function applyFilters() {
    const q = document.getElementById('search').value.trim().toLowerCase();
    const t = document.getElementById('filter-type').value;
    cy.nodes().forEach(n => {
      const d = n.data();
      const hay = [d.label, d.id, d.description, (d.tags || []).join(' '), d.body].join(' ').toLowerCase();
      n.toggleClass('dim', Boolean((t && d.type !== t) || (q && !hay.includes(q))));
    });
    cy.edges().forEach(edge => edge.toggleClass('dim', edge.source().hasClass('dim') || edge.target().hasClass('dim')));
    updateStats();
  }

  function esc(s) { return String(s ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch])); }
  function asJson(value) { return esc(JSON.stringify(value ?? {}, null, 2)); }
  function clearSelection() { cy.elements().unselect(); document.getElementById('detail-empty').hidden = false; document.getElementById('detail-content').hidden = true; }
  function typeChip(data) { return `<span class="type-chip" style="background:${esc(data.color)}">${esc(data.type)}</span>`; }
  function targetToId(href) { const base = String(href || '').split('#')[0]; if (!base.endsWith('.md')) return null; return (base.startsWith('/') ? base.slice(1) : base).replace(/\.md$/, ''); }

  function showDetail(conceptId, tab='detail') {
    const data = nodeIndex[conceptId]; if (!data) return;
    cy.elements().unselect(); cy.getElementById(conceptId).select();
    document.getElementById('detail-empty').hidden = true;
    const content = document.getElementById('detail-content'); content.hidden = false;
    const tabs = ['detail','body','links','citations','log','diagnostics'];
    const labels = {detail:'详情',body:'正文',links:'链接',citations:'引用',log:'日志',diagnostics:'诊断'};
    let html = `<div class="tabs">${tabs.map(t => `<button class="tab ${t===tab?'active':''}" data-tab="${t}">${labels[t]}</button>`).join('')}</div>`;
    if (tab === 'detail') {
      html += `<header class="detail-header">${typeChip(data)}<h1>${esc(data.label)}</h1><div class="muted">${esc(conceptId)}</div></header><dl class="frontmatter"><dt>Description</dt><dd>${esc(data.description || '—')}</dd><dt>Path</dt><dd>${esc(data.path || '—')}</dd><dt>Timestamp</dt><dd>${esc(data.timestamp || '—')}</dd><dt>Tags</dt><dd>${(data.tags||[]).map(t=>`<span class="tag">${esc(t)}</span>`).join('') || '—'}</dd></dl><h3>Resource</h3><pre>${asJson(data.resource)}</pre><h3>Frontmatter</h3><pre>${asJson(data.frontmatter)}</pre>`;
    } else if (tab === 'body') {
      html += `<div id="detail-body">${marked.parse(data.body || '', {gfm:true, breaks:false})}</div>`;
    } else if (tab === 'links') {
      const out = cy.edges(`[source = "${CSS.escape(conceptId)}"]`).map(e => e.target().id());
      const inc = backlinks[conceptId] || [];
      html += `<h2>Outgoing links</h2><ul>${out.map(id=>`<li><a href="#" data-concept="${esc(id)}">${esc(nodeIndex[id]?.label || id)}</a> <span class="muted">(${esc(id)})</span></li>`).join('') || '<li>无</li>'}</ul><h2>Cited by / Backlinks</h2><ul>${inc.map(id=>`<li><a href="#" data-concept="${esc(id)}">${esc(nodeIndex[id]?.label || id)}</a> <span class="muted">(${esc(id)})</span></li>`).join('') || '<li>无</li>'}</ul>`;
    } else if (tab === 'citations') {
      html += `<h2>Citations</h2>${(data.citations||[]).map(c => `<div class="card"><strong>[${esc(c.number || '?')}]</strong> ${esc(c.text || c.raw)}</div>`).join('') || '<p>无 citation 条目。</p>'}`;
    } else if (tab === 'log') {
      html += `<h2>Log Timeline</h2>${bundle.logs.map(g => `<div class="card"><h3>${esc(g.date)}</h3><div class="muted">${esc(g.path)}</div><ul>${(g.entries||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`).join('') || '<p>未找到 log.md 日期条目。</p>'}`;
    } else if (tab === 'diagnostics') {
      html += `<h2>Diagnostics</h2><p class="muted">这里列出无法连接到现有 concept 的内部 Markdown links。</p><h3>Broken internal links (${bundle.brokenLinks.length})</h3>${bundle.brokenLinks.map(b => `<div class="card"><strong>${esc(b.source)}</strong> — ${esc(b.label)} → <code>${esc(b.target)}</code><br><span class="muted">${esc(b.reason)}</span></div>`).join('') || '<p>无断链。</p>'}<h3>Index links (${bundle.indexLinks.length})</h3><pre>${asJson(bundle.indexLinks)}</pre>`;
    }
    content.innerHTML = html;
    content.querySelectorAll('[data-tab]').forEach(btn => btn.addEventListener('click', () => showDetail(conceptId, btn.dataset.tab)));
    content.querySelectorAll('[data-concept]').forEach(a => a.addEventListener('click', e => { e.preventDefault(); showDetail(a.dataset.concept, 'detail'); }));
    content.querySelectorAll('#detail-body a[href]').forEach(a => {
      const id = targetToId(a.getAttribute('href'));
      if (id && nodeIndex[id]) {
        a.className = 'internal'; a.href = 'javascript:void(0)';
        a.addEventListener('click', e => { e.preventDefault(); showDetail(id, 'detail'); });
      } else {
        a.className = 'external'; a.target = '_blank'; a.rel = 'noopener';
      }
    });
    cy.animate({ center: { eles: cy.getElementById(conceptId) }, zoom: Math.max(cy.zoom(), .9) }, { duration: 180 });
  }

  const initial = bundle.nodes.find(n => n.data.type === 'SDK Overview') || bundle.nodes[0];
  if (initial) showDetail(initial.data.id, 'detail');
})();
</script>
</body>
</html>
'''


def generate_extended(bundle: Path, output: Path, name: str) -> tuple[int, str]:
    data = collect_bundle_data(bundle, name)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(data), encoding="utf-8")
    return data["meta"]["nodeCount"], f"generated {output} with {data['meta']['nodeCount']} concept nodes, {data['meta']['edgeCount']} links, {data['meta']['brokenLinkCount']} broken links"


def main() -> int:
    parser = argparse.ArgumentParser(description="Visualize an OKF bundle using official visualizer or local extended fallback")
    parser.add_argument("bundle", type=Path, help="Path to OKF bundle directory")
    parser.add_argument("--out", type=Path, help="Output HTML path; defaults to <bundle>/viz.html")
    parser.add_argument("--name", default="OKF Bundle Visualization", help="HTML title")
    parser.add_argument("--mode", choices=("auto", "official", "extended"), default="auto", help="Visualization mode; default: auto")
    args = parser.parse_args()

    root = args.bundle.resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit(f"bundle path does not exist or is not a directory: {root}")
    output = args.out.resolve() if args.out else root / "viz.html"

    if args.mode in {"auto", "official"}:
        ok, message = run_official_visualizer(root, output, args.name)
        if ok:
            print(message)
            return 0
        if args.mode == "official":
            print(message, file=sys.stderr)
            return 1
        print(f"official visualizer unavailable; falling back to local extended viewer: {message}", file=sys.stderr)

    _, message = generate_extended(root, output, args.name)
    print(message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
