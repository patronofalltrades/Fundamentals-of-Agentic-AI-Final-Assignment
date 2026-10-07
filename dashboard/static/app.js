const $ = (id) => document.getElementById(id);
const api = async (path) => { const response = await fetch(path); if (!response.ok) throw new Error(`API ${response.status}`); return response.json(); };
const text = (node, value) => { node.textContent = String(value); return node; };
const el = (name, className, value) => { const node = document.createElement(name); if (className) node.className = className; if (value !== undefined) text(node, value); return node; };
const link = (href, label) => { const a = el('a', '', label); a.href = href; return a; };
let offset = 0;
let topic = '';
let query = '';

function showCoverage(summary) {
  const values = [
    ['Source rows', summary.coverage.source_rows],
    ['Nonempty rows', summary.coverage.nonempty_rows],
    ['Distinct texts', summary.coverage.distinct_nonempty_texts],
    ['Completed rows', summary.coverage.completed_rows],
    ['Empty rows', summary.coverage.empty_rows],
  ];
  for (const [label, value] of values) {
    const card = el('div', 'metric'); card.append(el('strong', '', value.toLocaleString()), el('span', '', label)); $('coverage').append(card);
  }
  text($('source-note'), `${summary.source.basename} • ${summary.note}`);
}
function showStatus(summary) {
  for (const [label, value] of Object.entries({Grouping: summary.analysis.grouping, Ranking: summary.analysis.ranking, Recommendations: summary.analysis.recommendations, Verification: summary.quality.blind_verifier, 'Human evaluation': summary.quality.human_evaluation})) {
    const card = el('div', 'status-card'); card.append(el('strong', value === 'pending' ? 'pending' : 'ready', value.replaceAll('_', ' ')), el('span', '', label)); $('status').append(card);
  }
}
function showTopics(summary) {
  const entries = Object.entries(summary.raw_labels.topic).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]));
  const max = Math.max(1, ...entries.map(x => x[1]));
  for (const [name, count] of entries) {
    const row = el('div', 'bar-row'); const track = el('div', 'bar-track'); const fill = el('div', 'bar-fill'); fill.style.width = `${100 * count / max}%`; track.append(fill); row.append(el('span', '', name), track, el('strong', '', count)); $('topics').append(row);
  }
  for (const name of ['access','usability','playback','downloads','catalog','billing','support','other']) {
    const option = el('option', '', name); option.value = name; $('topic-filter').append(option);
  }
}
async function showIssues() {
  const data = await api('/api/issues');
  if (!data.items.length) { $('issues').append(el('p', 'note', 'Pending accepted issue membership. No issue ranking has been produced.')); return; }
  for (const item of data.items) {
    const card = el('article', 'issue'); card.append(el('h3', '', `${item.issue_id} · ${item.title}`), el('p', '', `Priority score ${item.priority_score} · ${item.review_count} supporting reviews · mean severity ${item.mean_severity}`), link(`/api/issues/${encodeURIComponent(item.issue_id)}`, 'Inspect saved issue data'));
    const button = el('button', '', 'Show evidence'); button.addEventListener('click', async () => { const detail = await api(`/api/issues/${encodeURIComponent(item.issue_id)}`); const list = el('div', 'review-list'); for (const r of detail.reviews.items) list.append(reviewCard(r)); card.append(list); button.remove(); }); card.append(button); $('issues').append(card);
  }
}
async function showRecommendations() {
  const data = await api('/api/recommendations');
  if (!data.items.length) { $('recommendations').append(el('p', 'note', 'Pending saved recommendation and claim review.')); return; }
  $('recommendations').append(el('p', 'note', `Status: ${data.status.replaceAll('_', ' ')}. Review claims before a product decision.`));
  for (const item of data.items) { const card = el('article', 'recommendation'); card.append(el('p', '', item.text), el('small', '', 'Supporting issues: ')); for (const id of item.issue_ids) { card.append(link(`/api/issues/${encodeURIComponent(id)}`, id), document.createTextNode(' ')); } $('recommendations').append(card); }
}
function reviewCard(item) {
  const card = el('article', 'review'); card.append(el('span', 'tag', item.topic), el('span', 'tag', item.intent), el('span', 'tag', `Severity ${item.severity}`));
  card.append(el('blockquote', '', `“${item.evidence_quote}”`), el('small', '', `Source row ${item.row_index} · ${item.is_cached ? 'exact-text reuse' : 'direct result'} · ${item.needs_review ? 'needs review' : 'no review flag'}`));
  const button = el('button', '', 'View saved record');
  button.addEventListener('click', async () => {
    try {
      const detail = await api(`/api/reviews/${item.row_index}`);
      const panel = el('div', 'record-detail');
      panel.append(el('p', '', `Saved label: ${detail.topic} · ${detail.intent} · severity ${detail.severity} · sentiment ${detail.sentiment}`), el('p', '', `Source row hash: ${detail.source_sha256}`), el('p', '', `Label configuration: ${detail.label_config} · model: ${detail.model || 'unknown'} · prompt: ${detail.prompt_version || 'unknown'}`));
      card.append(panel); button.remove();
    } catch (error) { text($('error'), `Could not load record: ${error.message}`); }
  });
  card.append(button);
  return card;
}
async function loadReviews(reset=false) {
  if (reset) { offset = 0; $('reviews').replaceChildren(); }
  const data = await api(`/api/reviews?limit=20&offset=${offset}&topic=${encodeURIComponent(topic)}&q=${encodeURIComponent(query)}`);
  for (const item of data.items) $('reviews').append(reviewCard(item));
  offset += data.items.length; $('more').hidden = offset >= data.total;
  if (!data.total) $('reviews').append(el('p', 'note', 'No saved reviews match these filters.'));
}
async function main() {
  try {
    const summary = await api('/api/summary'); showCoverage(summary); showStatus(summary); showTopics(summary);
    await Promise.all([showIssues(), showRecommendations(), loadReviews()]);
    $('topic-filter').addEventListener('change', (event) => { topic = event.target.value; loadReviews(true).catch(error => text($('error'), error.message)); });
    $('search-form').addEventListener('submit', (event) => { event.preventDefault(); query = $('quote-search').value.trim(); loadReviews(true).catch(error => text($('error'), error.message)); });
    $('more').addEventListener('click', () => loadReviews().catch(error => text($('error'), error.message)));
  } catch (error) { text($('error'), `Could not load saved results: ${error.message}`); }
}
main();
