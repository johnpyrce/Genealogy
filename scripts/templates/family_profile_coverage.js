function renderProfileCoverage(data) {
 const coverage = data.coverage;
 const element = id => document.getElementById(id);
 const sourcePicker = element('coverage-source-picker');
 const placePicker = element('coverage-place-picker');
 const groups = element('coverage-groups');
 const dialog = element('coverage-breakdown');
 const status = element('coverage-status');
 const statusControl = element('coverage-status-control');
 const list = element('coverage-breakdown-records');
 const make = (tag, content) => {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  return node;
 };
 let details = [];
 function renderBreakdown() {
  const entries = details.filter(({value}) => statusControl.hidden ||
   (status.value === 'recorded' ? value !== undefined : value === undefined));
  element('coverage-breakdown-count').textContent = `${entries.length.toLocaleString()} records`;
  const items = document.createDocumentFragment();
  for (const {record, value} of entries) {
   const item = make('li');
   item.append(make('strong', record.name));
   if (value !== undefined) item.append(` · ${value}`);
   item.append(make('small', [record.event, record.reference].filter(Boolean).join(' · ')));
   items.append(item);
  }
  list.replaceChildren(items);
 }

 function showBreakdown(title, entries, available) {
  details = entries;
  element('coverage-breakdown-title').textContent = title;
  statusControl.hidden = available === 'all';
  if (!statusControl.hidden) status.value = available;
  renderBreakdown();
  dialog.showModal();
 }

 status.addEventListener('change', renderBreakdown);
 let locations = new Map();
 placePicker.addEventListener('change', () => {
  const place = placePicker.value;
  if (!place) return;
  showBreakdown(place, locations.get(place).map(record => ({
   record, value: [record.date, record.coordinates].filter(Boolean).join(' · ') || undefined,
  })), 'all');
  placePicker.value = '';
 });

 function renderGroup(group) {
  const collapsible = group.title.startsWith('Other fields') || group.title.startsWith('Evidence') ||
   group.title === 'Event dates';
  const card = make(collapsible ? 'details' : 'section');
  card.className = 'coverage-group';
  card.append(make(collapsible ? 'summary' : 'h3', group.title));
  for (const row of group.rows) {
   const indices = row.eligible ?? group.records.map((_, index) => index);
   const total = indices.length;
   const count = row.values === null ? null : Object.keys(row.values).length;
   const actionable = count !== null && total > 0;
   const label = make(actionable ? 'button' : 'div');
   label.className = 'coverage-row';
   const amount = make('span', count === null ? 'Unavailable' : total
    ? `${count.toLocaleString()} of ${total.toLocaleString()} · ${Math.round(100 * count / total)}%`
    : 'No eligible records');
   amount.className = 'coverage-amount';
   const bar = make(actionable ? 'progress' : 'span');
   if (actionable) {
    bar.max = total;
    bar.value = count;
    bar.setAttribute('aria-hidden', 'true');
    label.type = 'button';
    label.setAttribute('aria-haspopup', 'dialog');
    label.addEventListener('click', () => showBreakdown(row.label,
     indices.map(i => ({record: group.records[i], value: row.values[i]})), count ? 'recorded' : 'unrecorded'));
   }
   label.append(make('span', row.label), bar, amount);
   card.append(label);
  }
  return card;
 }

 function renderSource() {
  const source = coverage.sources[Number(sourcePicker.value)];
  element('coverage-source').textContent = data.gedcom
   ? `${source.label} · People and Families count records. Event dates and Places count recorded event entries.`
   : `${source.label} · Unavailable fields have no dedicated registry column.`;
  locations = new Map();
  for (const event of source.events ?? []) {
   for (const place of event.locations) {
    if (!locations.has(place)) locations.set(place, []);
    locations.get(place).push(event);
   }
  }
  placePicker.replaceChildren(new Option('Select a place', ''));
  for (const place of [...locations.keys()].sort((a, b) => a.localeCompare(b))) {
   placePicker.add(new Option(`${place} (${locations.get(place).length})`, place));
  }
  element('coverage-place-control').hidden = locations.size === 0;
  groups.replaceChildren(...source.groups.map(renderGroup));
 }

 coverage.sources.forEach(({label}, i) => sourcePicker.add(new Option(label, i)));
 element('coverage-source-control').hidden = coverage.sources.length === 1;
 sourcePicker.addEventListener('change', renderSource);
 renderSource();
}
