import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { buildSceneRegistry, SCENE_FAMILIES, sceneForBranch } from '../../frontend/natbirzha/js/active_production/scene_registry.mjs';
import { renderActiveProductionScene } from '../../frontend/natbirzha/js/active_production/scene.mjs';
import { paint } from '../../frontend/natbirzha/js/active_production/render.mjs';
import { createTimingGameState } from '../../frontend/natbirzha/js/active_production/gameplay.mjs';

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

test('the fullscreen scene escapes labels and exposes the timing game without movement controls', () => {
  const html = renderActiveProductionScene(
    { name: '<script>broken</script>' },
    { selected_branch_id: 'ore_mining', facilities: [{
      branch_id: 'ore_mining', sector_id: 'resources', name: 'Шахта', scene: sceneForBranch('ore_mining', 'resources'),
    }] },
  );

  assert.ok(!html.includes('<script>'));
  assert.ok(!html.includes('data-active-joystick'));
  assert.ok(html.includes('data-active-exit'));
  assert.ok(!html.includes('data-active-order-select'));
  assert.ok(html.includes('data-active-tap'));
  assert.ok(html.includes('×5'));
  assert.ok(html.includes('aria-label="Мини-игра: попади стрелкой в золотую или синюю зону"'));
});

test('the rhythm mini-game renders colored target zones, pointer, charge and hit feedback', () => {
  const calls = { gradients: 0, fills: 0, strokes: 0, texts: [] };
  const ctx = {
    clearRect() {}, fillRect() { calls.fills += 1; }, strokeRect() {},
    beginPath() {}, moveTo() {}, lineTo() {}, closePath() {},
    fill() {}, stroke() { calls.strokes += 1; }, arc() {}, fillText(text) { calls.texts.push(text); },
    save() {}, restore() {},
    createLinearGradient() { calls.gradients += 1; return { addColorStop() {} }; },
    createRadialGradient() { calls.gradients += 1; return { addColorStop() {} }; },
  };

  paint(ctx, 360, 240, { scene_family: 'materials', microvariant: 0, workstation: 'ЛИНИЯ' }, {
    ...createTimingGameState({ pointer_angle: 30, target_angle: 60, direction: 1,
      speed: 132, charge: 4, streak: 2, multiplier: 2, server_now: '2026-10-11T12:00:00' }, 1000),
    lastResult: 'gold',
  }, 1250);

  assert.ok(calls.gradients >= 2, 'the wheel and center use layered shading');
  assert.ok(calls.strokes >= 4, 'the wheel track and colored target zones should be painted');
  assert.ok(calls.texts.includes('×2.00'));
  assert.ok(calls.texts.includes('ЗОЛОТО +2'));
  assert.ok(calls.texts.includes('СИНИЙ +1'));
  assert.ok(calls.texts.includes('ТОЧНО!'));
});
