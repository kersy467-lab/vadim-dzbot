import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { buildSceneRegistry, SCENE_FAMILIES, sceneForBranch } from '../../frontend/natbirzha/js/active_production/scene_registry.mjs';
import { renderActiveProductionScene } from '../../frontend/natbirzha/js/active_production/scene.mjs';

const pythonCatalog = JSON.parse(execFileSync('python', ['-c', [
  'import json',
  'from backend.natbirzha.next_game_catalog import get_next_game_catalog',
  'print(json.dumps(get_next_game_catalog(), ensure_ascii=True))',
].join(';')], { encoding: 'utf8' }));

test('scene registry builds a themed scene for every current branch ID', () => {
  const registry = buildSceneRegistry(pythonCatalog);
  const branchIds = pythonCatalog.flatMap((corporation) => corporation.branches.map((branch) => branch.id));

  assert.equal(Object.keys(SCENE_FAMILIES).length, 7);
  assert.equal(registry.size, branchIds.length);
  assert.equal(registry.size, 205);
  for (const id of branchIds) {
    const scene = registry.get(id);
    assert.ok(scene?.scene_family);
    assert.ok(scene?.visual_pickup && scene?.workstation && scene?.delivery_marker && scene?.vehicle);
  }
  assert.equal(registry.get('ore_mining').scene_family, 'resources');
  assert.equal(registry.get('logistics').scene_family, 'infrastructure');
  assert.notEqual(registry.get('ore_mining').workstation, registry.get('logistics').workstation);
});

test('the fullscreen scene escapes company and facility labels and exposes phone controls', () => {
  const html = renderActiveProductionScene(
    { name: '<script>broken</script>' },
    { selected_branch_id: 'ore_mining', facilities: [{
      branch_id: 'ore_mining', sector_id: 'resources', name: 'Шахта', scene: sceneForBranch('ore_mining', 'resources'),
    }] },
  );

  assert.ok(!html.includes('<script>'));
  assert.ok(html.includes('data-active-joystick'));
  assert.ok(html.includes('data-active-exit'));
  assert.ok(html.includes('aria-label="2D-сцена активного производства"'));
});
