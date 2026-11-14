const { test } = require('node:test');
const assert = require('node:assert/strict');
const { publish } = require('../scripts/link-check-report.cjs');
const SHA = 'a'.repeat(40), TRUSTED = 'b'.repeat(40), BASE = 'c'.repeat(40);
const TREE = 'd'.repeat(40);
function fixture() {
  const writes = [], notices = [];
  const repository = { id: 1, default_branch: 'main' };
  const run = { id: 10, conclusion: 'success', event: 'pull_request', repository,
    head_sha: SHA, head_branch: 'contribution', head_repository: { id: 2 },
    workflow_id: 20, path: '.github/workflows/link-check-analysis.yaml', pull_requests: [] };
  const pr = { state: 'open', merged: false, base: { repo: repository, ref: 'main' },
    head: { sha: SHA, ref: 'contribution', repo: { id: 2 } }, labels: [{ name: 'check-links' }] };
  const context = { repo: { owner: 'Chain-Love', repo: 'chain-love' }, sha: TRUSTED,
    payload: { workflow_run: run, repository } };
  const state = { artifacts: [{ id: 30, name: 'lychee-output-v2', expired: false, size_in_bytes: 1 }],
    base: BASE, tree: TREE, truncated: false, reads: 0, changePR: false, report: { number: 4813, body: '## Link check report' } };
  const github = { rest: {
    actions: { getWorkflow: async args => { assert.equal(args.workflow_id, 'link-check-analysis.yaml'); return { data: { id: 20 } }; }, listWorkflowRunArtifacts: () => {},
      downloadArtifact: async () => ({ data: Buffer.from('zip') }) },
    repos: { compareCommits: async args => { assert.equal(args.base, TRUSTED); assert.equal(args.head, SHA);
      return { data: { merge_base_commit: { sha: state.base } } }; } },
    git: { getTree: async args => ({ data: { truncated: state.truncated,
      tree: [{ path: '.github', type: 'tree', mode: '040000', sha: args.tree_sha === SHA ? state.tree : TREE }] } }) },
    pulls: { get: async () => { state.reads++; const result = structuredClone(pr);
      if (state.changePR && state.reads === 2) result.head.sha = TRUSTED;
      return { data: result }; } },
    issues: { create: async args => writes.push(['issue', args]), createComment: async args => writes.push(['comment', args]) },
  }, paginate: async (_method, args) => { assert.equal(args.run_id, 10); return state.artifacts; } };
  const summary = { addRaw: () => summary, write: async () => {} };
  const core = { notice: message => notices.push(message), summary };
  return { run, pr, state, writes, notices, context, github, core,
    execute: () => publish({ github, context, core, parseArtifact: () => state.report }) };
}
test('fork PR with empty associated PR array comments only on verified PR', async () => {
  const f = fixture(); await f.execute();
  assert.equal(f.writes.length, 1); assert.equal(f.writes[0][0], 'comment');
  assert.equal(f.writes[0][1].issue_number, 4813); assert.match(f.writes[0][1].body, new RegExp(SHA));
});
for (const [name, mutate] of [
  ['stale SHA', f => f.pr.head.sha = TRUSTED],
  ['wrong fork', f => f.pr.head.repo.id = 3],
  ['wrong branch', f => f.pr.head.ref = 'other'],
  ['closed PR', f => f.pr.state = 'closed'],
  ['merged PR', f => f.pr.merged = true],
  ['missing label', f => f.pr.labels = []],
  ['wrong base', f => f.pr.base.ref = 'other'],
  ['PR changes during validation', f => f.state.changePR = true],
  ['changed .github tree', f => f.state.tree = 'e'.repeat(40)],
  ['old artifact', f => f.state.artifacts[0].name = 'lychee-output'],
  ['expired artifact', f => f.state.artifacts[0].expired = true],
  ['failed run', f => f.run.conclusion = 'failure'],
  ['other event', f => f.run.event = 'push'],
]) test(name, async () => { const f = fixture(); mutate(f); await f.execute(); assert.deepEqual(f.writes, []); });
for (const [name, mutate] of [
  ['wrong source repository', f => f.run.repository = { id: 3 }],
  ['wrong workflow ID', f => f.run.workflow_id = 99],
  ['wrong workflow path', f => f.run.path = '.github/workflows/evil.yaml'],
  ['incomplete tree', f => f.state.truncated = true],
  ['missing merge base', f => f.state.base = undefined],
  ['duplicate artifact', f => f.state.artifacts.push({ ...f.state.artifacts[0], id: 31 })],
  ['oversized artifact', f => f.state.artifacts[0].size_in_bytes = 11 * 1024 * 1024],
  ['missing PR number', f => f.state.report.number = null],
  ['API failure', f => f.github.rest.pulls.get = async () => { throw new Error('API failure'); }],
]) test(name, async () => { const f = fixture(); mutate(f); await assert.rejects(f.execute); assert.deepEqual(f.writes, []); });
function manual(f) { f.run.event = 'workflow_dispatch'; f.run.head_branch = 'main'; f.run.head_repository.id = 1;
  f.state.base = SHA; f.state.report.number = null; }
test('trusted manual report creates issue without PR metadata', async () => {
  const f = fixture(); manual(f); await f.execute(); assert.equal(f.writes[0][0], 'issue');
});
for (const [name, mutate] of [
  ['manual feature branch', f => f.run.head_branch = 'feature'],
  ['manual fork', f => f.run.head_repository.id = 3],
  ['manual non-ancestor', f => f.state.base = BASE],
  ['manual old scripts', f => f.state.tree = 'e'.repeat(40)],
]) test(name, async () => { const f = fixture(); manual(f); mutate(f); await f.execute(); assert.deepEqual(f.writes, []); });
test('manual PR metadata rejected', async () => {
  const f = fixture(); manual(f); f.state.report.number = 4813; await assert.rejects(f.execute); assert.deepEqual(f.writes, []);
});
test('artifact parser failure cannot publish', async () => {
  const f = fixture(); await assert.rejects(() => publish({ ...f, parseArtifact: () => { throw new Error('bad ZIP'); } }));
  assert.deepEqual(f.writes, []);
});
test('real ZIP crosses the Node/Python boundary and produces a fixed report', async () => {
  const { execFileSync } = require('node:child_process');
  const path = require('node:path');
  const f = fixture();
  const zip = execFileSync('python3', ['-c', [
    'import io, sys, zipfile',
    'buffer = io.BytesIO()',
    'with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:',
    '    archive.writestr("pr-number.txt", "4813\\n")',
    '    archive.write(sys.argv[1], "lychee/out.json")',
    'sys.stdout.buffer.write(buffer.getvalue())',
  ].join('\n'), path.join(__dirname, 'fixtures/lychee-v0.24.2.json')]);
  f.github.rest.actions.downloadArtifact = async () => ({ data: zip });
  await publish({ github: f.github, context: f.context, core: f.core });
  assert.equal(f.writes.length, 1);
  assert.match(f.writes[0][1].body, /HTTP 404/);
  assert.equal(f.writes[0][1].issue_number, 4813);
});
test('wrong PR number resolving to an ordinary issue fails closed', async () => {
  const f = fixture();
  f.github.rest.pulls.get = async () => { throw Object.assign(new Error('Not Found'), { status: 404 }); };
  await assert.rejects(f.execute); assert.deepEqual(f.writes, []);
});
test('wrong PR number resolving to a different PR fails closed', async () => {
  const f = fixture(); f.state.report.number = 1; f.pr.head.sha = TRUSTED;
  await f.execute(); assert.deepEqual(f.writes, []);
});
test('download size is checked independently from artifact metadata', async () => {
  const f = fixture(); f.github.rest.actions.downloadArtifact = async () => ({ data: Buffer.alloc(11 * 1024 * 1024) });
  await assert.rejects(f.execute); assert.deepEqual(f.writes, []);
});
