const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');

const WORKFLOW = '.github/workflows/link-check-analysis.yaml';
const ARTIFACT = 'lychee-output-v2';
const MAX_ZIP = 10 * 1024 * 1024;
const sha = value => typeof value === 'string' && /^[0-9a-f]{40}$/.test(value);

function matchingPR(pr, run, repository) {
  return pr.state === 'open' && !pr.merged &&
    pr.base?.repo?.id === repository.id && pr.base.ref === repository.default_branch &&
    pr.head?.sha === run.head_sha && pr.head.ref === run.head_branch &&
    pr.head.repo?.id === run.head_repository?.id &&
    pr.labels.some(label => label.name === 'check-links');
}

async function publish({ github, context, core, parseArtifact }) {
  const run = context.payload.workflow_run;
  const repository = context.payload.repository;
  const args = context.repo;
  const skip = async reason => {
    core.notice(reason);
    await core.summary.addRaw(`Link check report skipped: ${reason}`).write();
  };
  if (run.conclusion !== 'success' || !['pull_request', 'workflow_dispatch'].includes(run.event)) {
    return skip('Unsupported event or unsuccessful analysis.');
  }
  if (run.repository?.id !== repository.id || !sha(run.head_sha) || !sha(context.sha)) {
    throw new Error('Invalid source run');
  }
  const { data: workflow } = await github.rest.actions.getWorkflow({ ...args, workflow_id: 'link-check-analysis.yaml' });
  if (run.workflow_id !== workflow.id || run.path !== WORKFLOW) {
    throw new Error('Unexpected source workflow');
  }
  const manual = run.event === 'workflow_dispatch';
  if (manual && (run.head_repository?.id !== repository.id || run.head_branch !== repository.default_branch)) {
    return skip('Manual reports require the default branch of the base repository.');
  }

  // All tree reads use immutable commits, never the moving current PR diff.
  const { data: comparison } = await github.rest.repos.compareCommits({
    ...args, base: context.sha, head: run.head_sha,
  });
  const baseSHA = comparison.merge_base_commit?.sha;
  if (!sha(baseSHA)) throw new Error('Missing merge base');
  if (manual && baseSHA !== run.head_sha) return skip('Manual source is not a trusted default-branch ancestor.');
  const subtree = async commit => {
    const { data } = await github.rest.git.getTree({ ...args, tree_sha: commit });
    if (data.truncated) throw new Error('Incomplete tree');
    const entry = data.tree.find(item => item.path === '.github');
    if (!entry || entry.type !== 'tree' || entry.mode !== '040000' || !sha(entry.sha)) {
      throw new Error('Invalid .github tree');
    }
    return entry.sha;
  };
  // Manual runs must also use the current trusted workflow/scripts tree.
  if (await subtree(manual ? context.sha : baseSHA) !== await subtree(run.head_sha)) {
    return skip('Source changes .github; automatic publication is disabled.');
  }
  const artifacts = await github.paginate(github.rest.actions.listWorkflowRunArtifacts, {
    ...args, run_id: run.id, per_page: 100,
  });
  const candidates = artifacts.filter(item => item.name === ARTIFACT && !item.expired);
  if (!candidates.length) return skip('No v2 artifact; run the updated analysis workflow.');
  if (candidates.length !== 1 || candidates[0].size_in_bytes > MAX_ZIP) {
    throw new Error('Ambiguous or oversized artifact');
  }
  const { data } = await github.rest.actions.downloadArtifact({
    ...args, artifact_id: candidates[0].id, archive_format: 'zip',
  });
  const buffer = Buffer.from(data);
  if (buffer.length > MAX_ZIP) throw new Error('Archive too large');
  let report;
  if (parseArtifact) {
    report = parseArtifact(buffer, run.event);
  } else {
    const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'link-check-'));
    try {
      const archive = path.join(temporary, 'artifact.zip');
      fs.writeFileSync(archive, buffer, { flag: 'wx', mode: 0o600 });
      report = JSON.parse(execFileSync('python3', [
        path.join(__dirname, 'link-check-artifact.py'), archive, run.event,
      ], { encoding: 'utf8', maxBuffer: 1024 * 1024, timeout: 30000 }));
    } finally {
      fs.rmSync(temporary, { recursive: true, force: true });
    }
  }
  const body = `${report.body}\n\nCommit: \`${run.head_sha}\`\n\n[Analysis run](https://github.com/${args.owner}/${args.repo}/actions/runs/${run.id})`;
  if (body.length > 50000) throw new Error('Comment too large');
  if (manual) {
    if (report.number !== null) throw new Error('Unexpected PR metadata');
    await github.rest.issues.create({ ...args, title: 'Link Checker Report', body, labels: ['report', 'automated issue'] });
  } else {
    if (!Number.isSafeInteger(report.number) || report.number < 1) throw new Error('Invalid PR number');
    const getPR = async () => (await github.rest.pulls.get({ ...args, pull_number: report.number })).data;
    if (!matchingPR(await getPR(), run, repository)) return skip('PR metadata, label or state no longer matches.');
    // Recheck immediately before the write; the comment names the immutable SHA.
    if (!matchingPR(await getPR(), run, repository)) return skip('PR changed during validation.');
    await github.rest.issues.createComment({ ...args, issue_number: report.number, body });
  }
  await core.summary.addRaw('Link check report published.').write();
}
module.exports = { publish, matchingPR };
