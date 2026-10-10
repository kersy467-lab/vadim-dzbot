import assert from 'node:assert/strict';
import test from 'node:test';
import { renderPartnerships } from '../frontend/natbirzha/js/screens/next_game_contracts.js';

const data = {
  cash: 10000, companies: [{ id: 2, name: 'Партнёр' }], items: [{ id: 'steel', name: 'Сталь', unit: 'т' }],
  blueprints: [], active_projects: 0, projects: [],
  supplies: [{ id: 1, kind: 'supply', status: 'OPEN', can_accept: true, item_name: '<script>',
    initiator_name: 'Покупатель', partner_name: 'Продавец', quantity: 100, delivered: 0,
    unit_price: 10, rate_per_hour: 20, duration_hours: 24, escrow_cash: 1000, batch: 5 }],
};

test('partnerships keep creation collapsed and show accept only to the recipient', () => {
  const markup = renderPartnerships(data);
  assert.doesNotMatch(markup, /data-partner-form/);
  assert.match(markup, /data-partner-tab="supply"/);
  assert.match(markup, /data-partner-tab="projects"/);
  assert.match(markup, /data-partner-respond="1" data-kind="supply" data-accept="true"/);
  assert.match(markup, /&lt;script&gt;/);
  const outgoing = renderPartnerships({ ...data, supplies: [{ ...data.supplies[0], can_accept: false }] });
  assert.doesNotMatch(outgoing, /data-partner-respond/);
  assert.match(outgoing, /Отозвать предложение/);
});

test('empty blueprints disable shared construction with the actual unlock reason', () => {
  const markup = renderPartnerships(data, { view: 'projects', showForm: true });
  assert.match(markup, /type="submit" disabled/);
  assert.match(markup, /Сначала откройте направление/);
  assert.doesNotMatch(markup, /data-partner-respond/);
});
