function packSpouseRows(rows, partners) {
 const byPerson = new Map();
 for (const row of rows) {
  row.members.forEach((id, column) => byPerson.set(id, {row, column}));
 }
 const placed = new Set();
 const blocks = [];
 for (const root of rows) {
  if (placed.has(root)) continue;
  const block = {rows: [], minX: 0, maxX: 0, minZ: 0, maxZ: 0};
  const occupied = new Map();
  function place(row, x, z) {
   const end = x + row.members.length - 1;
   if (!occupied.has(z)) occupied.set(z, []);
   occupied.get(z).push({start: x, end});
   placed.add(row);
   block.rows.push({row, x, z});
   block.minX = Math.min(block.minX, x);
   block.maxX = Math.max(block.maxX, end);
   block.minZ = Math.min(block.minZ, z);
   block.maxZ = Math.max(block.maxZ, z);
  }
  place(root, 0, 0);
  // Walk between spouse-linked rows. Align each new row with the spouse's
  // column, and take the nearest depth where the sibling row fits.
  for (let i = 0; i < block.rows.length; i++) {
   const {row, x, z} = block.rows[i];
   row.members.forEach((id, column) => {
    for (const partner of partners.get(id) || []) {
     const other = byPerson.get(partner);
     if (!other || placed.has(other.row)) continue;
     const start = x + column - other.column;
     const end = start + other.row.members.length - 1;
     for (let step = 1; ; step++) {
      const depth = z + (step % 2 ? 1 : -1) * Math.ceil(step / 2);
      if ((occupied.get(depth) || []).some(row => start <= row.end && end >= row.start)) continue;
      place(other.row, start, depth);
      break;
     }
    }
   });
  }
  blocks.push(block);
 }
 return blocks;
}

function layoutGenerationLayers(people, families) {
 const positions = new Map();
 const tiers = new Map();
 const birthFamily = new Map();
 const partners = new Map();
 for (const person of people) {
  const generation = person.component_generation;
  if (!tiers.has(generation)) tiers.set(generation, []);
  tiers.get(generation).push(person.id);
 }
 for (const family of families) {
  for (const child of family.children) {
   if (!birthFamily.has(child)) birthFamily.set(child, family);
  }
  if (family.parents.length === 2) {
   const [a, b] = family.parents;
   if (!partners.has(a)) partners.set(a, []);
   if (!partners.has(b)) partners.set(b, []);
   partners.get(a).push(b);
   partners.get(b).push(a);
  }
 }

 const layers = [];
 const generations = [...tiers.keys()].sort((a, b) => a - b);
 const levelGap = 120;
 const personGap = 34;
 const spouseGap = 30;
 const depthGap = 68;
 for (const generation of generations) {
  const ids = tiers.get(generation);
  const groups = [];
  const groupByFamily = new Map();
  // Keep each group of recorded siblings together and use the parent position
  // to order its branch on the next plane.
  for (const id of ids) {
   const birth = birthFamily.get(id);
   if (!birth) continue;
   if (!groupByFamily.has(birth.id)) {
    const parents = birth.parents.map(parent => positions.get(parent)).filter(Boolean);
    const group = {
     members: [],
     parentX: parents.reduce((sum, p) => sum + p.x, 0) / (parents.length || 1),
     parentZ: parents.reduce((sum, p) => sum + p.z, 0) / (parents.length || 1),
    };
    groupByFamily.set(birth.id, group);
    groups.push(group);
   }
   groupByFamily.get(birth.id).members.push(id);
  }
  for (const id of ids) {
   if (!birthFamily.has(id)) groups.push({members: [id], parentX: 0, parentZ: 0});
  }
  groups.sort((a, b) => a.parentZ - b.parentZ || a.parentX - b.parentX || a.members[0] - b.members[0]);

  const blocks = packSpouseRows(groups, partners);
  const blocksPerLane = Math.ceil(blocks.length / Math.ceil(Math.sqrt(blocks.length)));
  const lanes = [];
  for (let start = 0; start < blocks.length; start += blocksPerLane) {
   const items = blocks.slice(start, start + blocksPerLane);
   const width = items.reduce((sum, block) => sum + (block.maxX - block.minX + 2) * personGap, -2 * personGap);
   const depth = Math.max(...items.map(block => (block.maxZ - block.minZ) * spouseGap));
   lanes.push({items, width, depth});
  }
  const totalDepth = lanes.reduce((sum, lane) => sum + lane.depth + depthGap, -depthGap);
  const y = ((generations.length + 1) / 2 - generation) * levelGap;
  let laneZ = -totalDepth / 2;
  for (const lane of lanes) {
   let blockX = -lane.width / 2;
   for (const block of lane.items) {
    const blockZ = laneZ + lane.depth / 2 - (block.minZ + block.maxZ) * spouseGap / 2;
    for (const {row, x, z} of block.rows) {
     row.members.forEach((id, column) => {
      positions.set(id, {id, x: blockX + (x - block.minX + column) * personGap, y, z: blockZ + z * spouseGap});
     });
    }
    blockX += (block.maxX - block.minX + 2) * personGap;
   }
   laneZ += lane.depth + depthGap;
  }
  const halfWidth = Math.max(52, ...lanes.map(lane => lane.width / 2 + 30));
  const halfDepth = Math.max(46, totalDepth / 2 + 30);
  layers.push({generation, y, halfWidth, halfDepth});
 }

 const links = [];
 for (const family of families) {
  const parents = family.parents.map(id => positions.get(id)).filter(Boolean);
  const children = family.children.map(id => positions.get(id)).filter(Boolean);
  if (!parents.length) continue;
  const [first, second] = parents;
  const origin = second ? {x: (first.x + second.x) / 2, y: first.y, z: (first.z + second.z) / 2} : first;
  if (second) links.push({from: first, to: second, ids: family.parents, children: family.children});
  for (const child of children) links.push({from: origin, to: child, ids: [...family.parents, child.id]});
 }
 return {positions, layers, links};
}

function rankedSurnames(people) {
 const counts = new Map();
 for (const {group} of people) counts.set(group, (counts.get(group) || 0) + 1);
 return [...counts.keys()].sort((a, b) => counts.get(b) - counts.get(a) || a.localeCompare(b, 'pl'));
}

function separateProjectedNodes(points, width, height, gap) {
 const margin = 7;
 const inside = (x, y) => x >= margin && y >= margin && x <= width - margin && y <= height - margin;
 const occupied = new Map();
 const cell = (x, y) => `${x},${y}`;
 function available(x, y) {
  if (!inside(x, y)) return false;
  const col = Math.floor(x / gap), row = Math.floor(y / gap);
  for (let dy = -1; dy <= 1; dy++) {
   for (let dx = -1; dx <= 1; dx++) {
    const nearby = occupied.get(cell(col + dx, row + dy)) || [];
    if (nearby.some(p => Math.hypot(p.x - x, p.y - y) < gap)) return false;
   }
  }
  return true;
 }
 const step = gap / 2;
 const maxRing = Math.ceil(Math.max(width, height) / step);
 return points.map(point => {
  const {x, y} = point;
  const displayed = {...point, anchorX: x, anchorY: y};
  // Zoomed-in views can extend beyond the canvas. Keep those positions so
  // the points enter the view in their proper place when zooming out.
  if (!inside(x, y)) return displayed;
  for (let ring = 1; !available(displayed.x, displayed.y) && ring <= maxRing; ring++) {
   let best = Infinity;
   for (let dy = -ring; dy <= ring; dy++) {
    for (let dx = -ring; dx <= ring; dx++) {
     if (Math.max(Math.abs(dx), Math.abs(dy)) !== ring) continue;
     const distance = dx * dx + dy * dy;
     if (distance >= best || !available(x + dx * step, y + dy * step)) continue;
     best = distance;
     displayed.x = x + dx * step;
     displayed.y = y + dy * step;
    }
   }
  }
  const key = cell(Math.floor(displayed.x / gap), Math.floor(displayed.y / gap));
  if (!occupied.has(key)) occupied.set(key, []);
  occupied.get(key).push(displayed);
  return displayed;
 });
}

// Breadth-first traversal groups shared ancestors at their nearest distance and
// retains each recorded connection, including routes through another branch.
function traceGenerations(start, adjacent) {
 const distance = new Map([[start, 0]]);
 const reverse = new Map();
 const queue = [start];
 for (let i = 0; i < queue.length; i++) {
  const child = queue[i];
  for (const parent of adjacent.get(child) || []) {
   if (!reverse.has(parent)) reverse.set(parent, new Set());
   reverse.get(parent).add(child);
   if (distance.has(parent)) continue;
   distance.set(parent, distance.get(child) + 1);
   queue.push(parent);
  }
 }
 return {distance, reverse};
}

function initGenerationLayers(data) {
 const canvas = document.getElementById('layers-canvas');
 const ctx = canvas.getContext('2d');
 const summary = document.getElementById('layers-summary');
 if (!ctx) {
  summary.textContent = 'This browser could not draw the generation layers.';
  return;
 }
 const tree = document.getElementById('layers-tree');
 const person = document.getElementById('layers-person');
 const detail = document.getElementById('layers-person-detail');
 const relatives = document.getElementById('layers-relatives');
 const back = document.getElementById('layers-back');
 const history = [];
 let marked = new Set();
 const legend = document.getElementById('layers-surnames');
 const issuesButton = document.getElementById('layers-issues-open');
 const issuesDialog = document.getElementById('layers-isolated');
 const isolatedList = document.getElementById('layers-isolated-list');
 const unplacedList = document.getElementById('layers-unplaced-list');
 const zoomOut = document.getElementById('layers-zoom-out');
 const zoomIn = document.getElementById('layers-zoom-in');
 const reset = document.getElementById('layers-reset');
 const components = new Map();
 const byId = new Map(data.people.map(p => [p.id, p]));
 const ancestorToggle = document.getElementById('layers-ancestors');
 const parentIndex = new Map();
 for (const family of data.families) {
  for (const child of family.children) {
   if (!parentIndex.has(child)) parentIndex.set(child, new Set());
   for (const parent of family.parents) {
    if (parent !== child && byId.has(parent)) parentIndex.get(child).add(parent);
   }
  }
 }
 let ancestry = null, branch = null, pinned = null, branchTip = null;
 const name = p => [p.first, p.surname].filter(Boolean).join(' ') || 'Name unknown';
 const palette = [
  '#0072b2', '#d55e00', '#009e73', '#cc79a7', '#e9ad00', '#67419a',
  '#56b4e9', '#96352b', '#78a22f', '#e98662', '#333b78', '#04b7b0',
  '#8c632d', '#ad3e85', '#476b35', '#ac91d2', '#20545a', '#c78737',
 ];
 const surnameColors = new Map(rankedSurnames(data.people).filter(group => group !== 'Unknown').map((group, index) =>
  [group, palette[index % palette.length]]));
 const surnameColor = group => surnameColors.get(group) ?? '#697574';

 function surnameKey(group, label) {
  const item = document.createElement('span');
  const swatch = document.createElement('span');
  swatch.className = 'layers-surname-swatch';
  swatch.style.backgroundColor = surnameColor(group);
  item.append(swatch, label);
  return item;
 }
 for (const p of data.people) {
  if (!components.has(p.component)) components.set(p.component, []);
  components.get(p.component).push(p);
 }
 const isIsolated = p => components.get(p.component).length === 1;
 const isolated = data.people.filter(isIsolated);
 issuesButton.textContent = isolated.length === 1 ? 'Data issue (1)' : `Data issues (${isolated.length})`;
 issuesButton.addEventListener('click', () => issuesDialog.showModal());
 const unplaced = data.people.filter(p => !isIsolated(p) && !p.component_generation);
 const trees = [...components.entries()]
  .filter(([, members]) => members.length > 1 && members[0].component_generation > 0)
  .sort((a, b) => b[1].length - a[1].length || a[0] - b[0]);
 tree.add(new Option('All people', ''));
 for (const [id, members] of trees) {
  const first = members.find(p => p.component_generation === 1);
  tree.add(new Option(`${name(first)} · ${members.length} people`, id));
 }
 document.getElementById('layers-tree-control').hidden = trees.length < 2;
 const unplacedButtons = new Map();
 for (const [list, people] of [[isolatedList, isolated], [unplacedList, unplaced]]) {
  for (const p of people) {
   const button = document.createElement('button');
   button.type = 'button';
   button.append(surnameKey(p.group, name(p)));
   button.addEventListener('click', () => {
    selectPerson(p.id);
    if (list === isolatedList) {
     issuesDialog.close();
     detail.focus();
    }
   });
   list.append(button);
   unplacedButtons.set(p.id, button);
  }
 }
 function generationLabel(p, prefix) {
  if (isIsolated(p)) return 'No recorded family connections';
  return p.component_generation ? `${prefix} ${p.component_generation}` : 'Generation unknown';
 }

 const defaultYaw = -0.46;
 const defaultPitch = 0.29;
 const minZoom = 0.65;
 const maxZoom = 2.5;
 let yaw = defaultYaw, pitch = defaultPitch, zoom = 1;
 let scene, selected = null, hovered = null, drag = null;
 let displayed = [];
 let scheduled = false;
 function requestDraw() {
  if (scheduled) return;
  scheduled = true;
  requestAnimationFrame(() => {
   scheduled = false;
   draw();
  });
 }
 function corners(layer) {
  const {y, halfWidth: x, halfDepth: z} = layer;
  return [{x:-x,y,z:-z}, {x,y,z:-z}, {x,y,z}, {x:-x,y,z}];
 }
 let radius, bounds, fit, markerLayout;
 function projector(angle, tilt) {
  const cosYaw = Math.cos(angle), sinYaw = Math.sin(angle);
  const cosPitch = Math.cos(tilt), sinPitch = Math.sin(tilt);
  const distance = 5 * radius;
  return point => {
   const x = point.x * cosYaw - point.z * sinYaw;
   const z = point.x * sinYaw + point.z * cosYaw;
   const depth = z * cosPitch + point.y * sinPitch;
   const scale = distance / (distance - depth);
   return {x: x * scale, y: (z * sinPitch - point.y * cosPitch) * scale, depth};
  };
 }
 function cameraExtent(project) {
  return bounds.reduce(({x, y}, point) => {
   const p = project(point);
   return {x: Math.max(x, Math.abs(p.x)), y: Math.max(y, Math.abs(p.y))};
  }, {x: 1, y: 1});
 }
 function loadTree() {
  const allPeople = tree.value === '';
  const members = allPeople ? data.people : components.get(Number(tree.value));
  const placed = members.filter(p => p.component_generation > 0 && !isIsolated(p));
  scene = layoutGenerationLayers(placed, data.families);
  markerLayout = null;
  bounds = scene.layers.flatMap(corners);
  radius = bounds.reduce((max, p) => Math.max(max, Math.hypot(p.x, p.y, p.z)), 1);
  fit = cameraExtent(projector(defaultYaw, defaultPitch));
  const count = `${placed.length} people plotted`;
  const generations = scene.layers.length === 1 ? '1 generation' : `${scene.layers.length} generations`;
  summary.textContent = placed.length ? `${count} · ${generations}` : count;
  if (allPeople && trees.length > 1) summary.append(' · Generations are numbered within each connected tree');
  if (allPeople && unplaced.length) summary.append(` · ${unplaced.length} with no established generation`);
  canvas.hidden = !placed.length;
  issuesButton.hidden = !allPeople || !isolated.length;
  document.getElementById('layers-unplaced').hidden = !allPeople || !unplaced.length;
  const surnames = rankedSurnames(placed);
  legend.replaceChildren(...surnames.slice(0, 6).map(group =>
   surnameKey(group, group === 'Unknown' ? 'Unknown surname' : group)));
  if (surnames.length > 6) legend.append(`+${surnames.length - 6} more surnames`);
  person.replaceChildren(new Option('Select a person', ''));
  for (const p of [...members].sort((a, b) => name(a).localeCompare(name(b)) || a.id - b.id)) {
   person.add(new Option(`${name(p)} · ${generationLabel(p, 'Gen')}`, p.id));
  }
  person.disabled = !members.length;
  history.length = 0;
  selectPerson(null, false);
  resetView();
 }
 function resetView() {
  yaw = defaultYaw;
  pitch = defaultPitch;
  zoom = 1;
  hovered = null;
  updateZoom();
 }
 function updateZoom() {
  zoomOut.disabled = !scene.layers.length || zoom <= minZoom;
  zoomIn.disabled = !scene.layers.length || zoom >= maxZoom;
  reset.disabled = !scene.layers.length;
  requestDraw();
 }
 function scaleZoom(factor) {
  zoom = Math.max(minZoom, Math.min(maxZoom, zoom * factor));
  updateZoom();
 }
 function recordedRelatives(id) {
  const groups = {Parents: new Set(), Partners: new Set(), Children: new Set(), Siblings: new Set()};
  for (const family of data.families) {
   if (family.children.includes(id)) {
    family.parents.forEach(parent => groups.Parents.add(parent));
    family.children.forEach(child => groups.Siblings.add(child));
   }
   if (family.parents.includes(id)) {
    family.parents.forEach(parent => groups.Partners.add(parent));
    family.children.forEach(child => groups.Children.add(child));
   }
  }
  for (const family of data.families) {
   if (family.parents.some(parent => groups.Parents.has(parent))) {
    family.children.forEach(child => groups.Siblings.add(child));
   }
  }
  for (const ids of Object.values(groups)) ids.delete(id);
  return groups;
 }
 function previewAncestor(id) {
  branchTip = id;
  for (const label of relatives.querySelectorAll('.ancestor-color')) {
   label.classList.toggle('ancestor-associated', id !== null && Number(label.dataset.person) === id);
  }
  branch = id === null ? null : traceGenerations(id, ancestry.reverse).distance;
  requestDraw();
 }
 function renderAncestors(id) {
  ancestry = traceGenerations(id, parentIndex);
  marked = new Set(ancestry.distance.keys());
  if (marked.size === 1) {
   relatives.textContent = 'No parents recorded';
   return;
  }
  const instructions = document.createElement('p');
  instructions.textContent = 'Hover, focus, or select an ancestor to highlight their name and their parents’ matching labels.';
  relatives.append(instructions);
  function coloredName(personId, prefix = '') {
   const label = document.createElement('span');
   label.className = 'ancestor-color';
   label.dataset.person = personId;
   label.textContent = prefix + name(byId.get(personId));
   return label;
  }
  let previousDepth = 0;
  for (const [ancestor, depth] of ancestry.distance) {
   if (!depth) continue;
   if (depth !== previousDepth) {
    const heading = document.createElement('h4');
    heading.textContent = ['','Parents','Grandparents','Great-grandparents'][depth] || `Ancestors · ${depth} generations back`;
    relatives.append(heading);
    previousDepth = depth;
   }
   const button = document.createElement('button');
   button.type = 'button';
   button.className = 'ancestor-entry';
   button.setAttribute('aria-pressed', 'false');
   button.append(coloredName(ancestor));
   const info = document.createElement('small');
   for (const child of ancestry.reverse.get(ancestor)) {
    info.append(coloredName(child, 'Parent of '));
   }
   if (!parentIndex.get(ancestor)?.size) {
    const endpoint = document.createElement('span');
    endpoint.className = 'ancestor-endpoint';
    endpoint.textContent = 'No parents recorded';
    info.append(endpoint);
   }
   button.append(info);
   button.addEventListener('pointerenter', () => previewAncestor(ancestor));
   button.addEventListener('pointerleave', () => previewAncestor(pinned));
   button.addEventListener('focus', () => previewAncestor(ancestor));
   button.addEventListener('blur', () => previewAncestor(pinned));
   button.addEventListener('click', () => {
    relatives.querySelector('[aria-pressed="true"]')?.setAttribute('aria-pressed', 'false');
    pinned = pinned === ancestor ? null : ancestor;
    button.setAttribute('aria-pressed', String(pinned !== null));
    previewAncestor(pinned);
   });
   relatives.append(button);
  }
 }
 ancestorToggle.addEventListener('change', () => selectPerson(selected, false));
 function selectPerson(id, remember = true) {
  if (remember && selected !== null && selected !== id) history.push(selected);
  back.disabled = !history.length;
  marked = new Set();
  ancestry = branch = pinned = branchTip = null;
  if (id === null) ancestorToggle.checked = false;
  ancestorToggle.parentElement.hidden = id === null;
  relatives.classList.toggle('ancestor-list', ancestorToggle.checked);
  relatives.replaceChildren();
  relatives.scrollTop = 0;
  selected = id;
  person.value = id ?? '';
  const p = byId.get(id);
  detail.replaceChildren();
  for (const [personId, button] of unplacedButtons) {
   button.setAttribute('aria-pressed', String(personId === id));
  }
  if (p) {
   const rank = generationLabel(p, 'Generation');
   const entry = surnameKey(p.group, name(p));
   const metadata = document.createElement('small');
   const dates = [p.birth === null ? '' : `Born ${p.birth}`, p.death === null ? '' : `Died ${p.death}`].filter(Boolean);
   metadata.textContent = [rank, ...dates].join(' · ');
   entry.append(document.createElement('br'), metadata);
   detail.append(entry);
   if (ancestorToggle.checked) {
    renderAncestors(id);
    requestDraw();
    return;
   }
   const groups = recordedRelatives(id);
   marked = new Set([id, ...groups.Parents, ...groups.Partners, ...groups.Children]);
   for (const [role, ids] of Object.entries(groups)) {
    const heading = document.createElement('h4');
    heading.textContent = role;
    relatives.append(heading);
    const members = [...ids].map(key => byId.get(key)).filter(Boolean)
     .sort((a, b) => name(a).localeCompare(name(b)) || a.id - b.id);
    if (!members.length) relatives.append('None recorded');
    for (const member of members) {
     const button = document.createElement('button');
     button.type = 'button';
     button.textContent = name(member);
     button.addEventListener('click', () => {
      selectPerson(member.id);
      detail.focus({preventScroll: true});
     });
     relatives.append(button);
    }
   }
  } else {
   detail.textContent = 'Select a person to see their recorded family.';
  }
  requestDraw();
 }
 function path(points, close = false) {
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (const p of points.slice(1)) ctx.lineTo(p.x, p.y);
  if (close) ctx.closePath();
 }
 function draw() {
  const width = canvas.clientWidth, height = canvas.clientHeight;
  if (!width || !height) return;
  const density = Math.min(window.devicePixelRatio || 1, 2);
  const pixelsWide = Math.round(width * density), pixelsHigh = Math.round(height * density);
  if (canvas.width !== pixelsWide || canvas.height !== pixelsHigh) {
   canvas.width = pixelsWide;
   canvas.height = pixelsHigh;
  }
  ctx.setTransform(density, 0, 0, density, 0, 0);
  ctx.clearRect(0, 0, width, height);
  displayed = [];
  if (!scene.layers.length) return;

  const project = projector(yaw, pitch);
  const baseScale = Math.min(Math.max(1, width - 50) / (2 * fit.x),
   Math.max(1, height - 54) / (2 * fit.y), 2);
  const scale = zoom * baseScale;
  const dotRadius = Math.min(3.3, Math.sqrt(width * height / (scene.positions.size * 35)));
  if (!markerLayout || markerLayout.width !== width || markerLayout.height !== height) {
   const initial = projector(defaultYaw, defaultPitch);
   const projected = [...scene.positions.values()].map(point => {
    const p = initial(point);
    return {id: point.id, x: width / 2 + p.x * baseScale, y: height / 2 + p.y * baseScale, depth: p.depth};
   });
   // Resolve collisions once in the home view. Invert its camera transform
   // at each person's depth so the marker then rotates rigidly with the tree.
   const markers = separateProjectedNodes(projected, width, height, dotRadius * 2 + 4).map(p => {
    const anchor = scene.positions.get(p.id);
    const units = (1 - p.depth / (5 * radius)) / baseScale;
    const dx = (p.x - p.anchorX) * units, dy = (p.y - p.anchorY) * units;
    const dz = dy * Math.sin(defaultPitch);
    return {id: p.id, x: anchor.x + dx * Math.cos(defaultYaw) + dz * Math.sin(defaultYaw),
     y: anchor.y - dy * Math.cos(defaultPitch),
     z: anchor.z - dx * Math.sin(defaultYaw) + dz * Math.cos(defaultYaw)};
   });
   markerLayout = {width, height, markers};
  }
  function screen(point) {
   const p = project(point);
   return {x: width / 2 + p.x * scale, y: height / 2 + p.y * scale, depth: p.depth};
  }
  ctx.font = '600 12px system-ui, sans-serif';
  ctx.textBaseline = 'middle';
  for (const layer of scene.layers) {
   const polygon = corners(layer).map(screen);
   path(polygon, true);
   ctx.fillStyle = layer.generation % 2 ? '#d9e7dcaa' : '#dce7eeaa';
   ctx.strokeStyle = '#a7bdb4';
   ctx.lineWidth = 1;
   ctx.fill();
   ctx.stroke();
   const anchor = polygon.reduce((left, point) => point.x < left.x ? point : left);
   const label = `Gen ${layer.generation}`;
   ctx.fillStyle = '#314e48';
   ctx.fillText(label, Math.max(8, anchor.x - ctx.measureText(label).width - 6), anchor.y);
  }
  const active = selected ?? hovered;
  const emphasized = branch || marked;
  const hasFocus = link => !ancestry && (link.ids.includes(active) || link.children?.includes(selected));
  const links = active === null ? scene.links : [
   ...scene.links.filter(link => !hasFocus(link)), ...scene.links.filter(hasFocus)
  ];
  for (const link of links) {
   const highlighted = hasFocus(link);
   path([screen(link.from), screen(link.to)]);
   ctx.strokeStyle = highlighted ? '#a24b29' : selected === null ? '#657e7359' : '#657e7326';
   ctx.lineWidth = highlighted ? 1.8 : 1;
   ctx.stroke();
  }
  if (ancestry) {
   // Trace just the relevant half of a couple's connector on a single branch.
   for (const link of scene.links) {
    if (link.children || !emphasized.has(link.to.id)) continue;
    for (const parent of link.ids.slice(0, -1)) {
     const position = scene.positions.get(parent);
     if (!position || !emphasized.has(parent)) continue;
     path([screen(position), screen(link.from), screen(link.to)]);
     ctx.strokeStyle = '#a24b29';
     ctx.lineWidth = 2;
     ctx.stroke();
    }
   }
  }
  displayed = markerLayout.markers.map(marker => {
   const anchor = screen(scene.positions.get(marker.id));
   return {id: marker.id, ...screen(marker), anchorX: anchor.x, anchorY: anchor.y};
  }).sort((a, b) => a.depth - b.depth);
  for (const p of displayed) {
   if (p.x === p.anchorX && p.y === p.anchorY) continue;
   path([{x: p.anchorX, y: p.anchorY}, p]);
   ctx.strokeStyle = emphasized.has(p.id) ? '#a24b29' : selected === null ? '#60756e80' : '#60756e26';
   ctx.lineWidth = 0.8;
   ctx.stroke();
  }
  for (const point of displayed) {
   const highlighted = point.id === active;
   ctx.beginPath();
   ctx.arc(point.x, point.y, highlighted ? dotRadius + 1.5 : dotRadius, 0, Math.PI * 2);
   const color = surnameColor(byId.get(point.id).group);
   ctx.fillStyle = selected === null || emphasized.has(point.id) ? color : color + '55';
   ctx.fill();
   ctx.strokeStyle = highlighted ? '#24353a' : emphasized.has(point.id) ? '#a24b29' : '#fff';
   ctx.lineWidth = highlighted ? 2 : 1;
   ctx.stroke();
  }
  const labels = [];
  const labelIds = ancestry ? [selected, branchTip, hovered, ...(branch || parentIndex.get(selected) || [])] : [selected, hovered, ...marked];
  for (const id of new Set(labelIds)) {
   const point = displayed.find(p => p.id === id);
   if (!point || point.x < 0 || point.x > width || point.y < 0 || point.y > height) continue;
   const text = name(byId.get(id));
   const span = Math.min(ctx.measureText(text).width, width - 16);
   const x = Math.max(8, Math.min(point.x + 9, width - span - 8));
   let y;
   for (let row = 0; row < height / 16; row++) {
    const candidate = point.y + (row % 2 ? 1 : -1) * (12 + 16 * Math.floor(row / 2));
    if (candidate < 9 || candidate > height - 9) continue;
    if (labels.some(box => Math.abs(box.y - candidate) < 16 && x < box.end + 4 && x + span + 4 > box.x)) continue;
    y = candidate;
    break;
   }
   if (y === undefined) continue;
   labels.push({x, end: x + span, y});
   path([point, {x: Math.max(x, Math.min(point.x, x + span)), y}]);
   ctx.strokeStyle = '#78665a';
   ctx.lineWidth = 1;
   ctx.stroke();
   ctx.strokeStyle = '#fff';
   ctx.lineWidth = 4;
   ctx.fillStyle = '#24353a';
   ctx.strokeText(text, x, y, span);
   ctx.fillText(text, x, y, span);
  }
 }
 function hit(event) {
  const bounds = canvas.getBoundingClientRect();
  const x = event.clientX - bounds.left - canvas.clientLeft;
  const y = event.clientY - bounds.top - canvas.clientTop;
  let nearest = null, distance = 10;
  for (const point of displayed) {
   const separation = Math.hypot(point.x - x, point.y - y);
   if (separation <= distance) {
    distance = separation;
    nearest = point.id;
   }
  }
  return nearest;
 }
 function rotate(horizontal, vertical) {
  yaw += horizontal;
  pitch = Math.max(0.08, Math.min(1.17, pitch + vertical));
  requestDraw();
 }
 canvas.addEventListener('pointerdown', event => {
  if (event.button !== 0 || drag) return;
  drag = {id:event.pointerId, x:event.clientX, y:event.clientY, moved:false};
  canvas.setPointerCapture(event.pointerId);
 });
 canvas.addEventListener('pointermove', event => {
  if (drag?.id === event.pointerId) {
   const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
   if (!drag.moved && Math.hypot(dx, dy) < 4) return;
   drag = {...drag, x:event.clientX, y:event.clientY, moved:true};
   hovered = null;
   rotate(dx * 0.009, dy * 0.007);
  } else {
   const id = hit(event);
   if (id === hovered) return;
   hovered = id;
   requestDraw();
  }
 });
 canvas.addEventListener('pointerup', event => {
  if (drag?.id !== event.pointerId) return;
  if (!drag.moved) selectPerson(hit(event));
  drag = null;
 });
 canvas.addEventListener('lostpointercapture', () => { drag = null; });
 canvas.addEventListener('pointerleave', () => { hovered = null; requestDraw(); });
 canvas.addEventListener('wheel', event => {
  const mode = event.deltaMode;
  if (!scene.layers.length || !event.deltaY || event.ctrlKey || event.metaKey) return;
  event.preventDefault();
  const pixelsPerUnit = mode === WheelEvent.DOM_DELTA_LINE ? 16
   : mode === WheelEvent.DOM_DELTA_PAGE ? canvas.clientHeight : 1;
  scaleZoom(Math.exp(-event.deltaY * pixelsPerUnit * 0.002));
 }, {passive:false});
 canvas.addEventListener('keydown', event => {
  const change = {ArrowLeft:[-0.12,0], ArrowRight:[0.12,0], ArrowUp:[0,-0.08], ArrowDown:[0,0.08]}[event.key];
  if (event.key === 'Home') resetView();
  else if (change) rotate(...change);
  else return;
  event.preventDefault();
 });
 tree.addEventListener('change', loadTree);
 back.addEventListener('click', () => {
  if (!history.length) return;
  selectPerson(history.pop(), false);
  if (back.disabled) detail.focus({preventScroll: true});
 });
 person.addEventListener('change', () => selectPerson(person.value ? Number(person.value) : null));
 zoomOut.addEventListener('click', () => scaleZoom(1 / 1.2));
 zoomIn.addEventListener('click', () => scaleZoom(1.2));
 reset.addEventListener('click', resetView);
 new ResizeObserver(requestDraw).observe(canvas);
 loadTree();
}
